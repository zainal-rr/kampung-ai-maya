from __future__ import annotations

import logging
import re
import time
from collections import deque
from difflib import SequenceMatcher
from typing import Any

from maya_core.permission_policy import contains_sensitive_info
from maya_core.provenance import provenance_from_source_channel
from maya_meet.approval import TelegramSender, request_meeting_owner_approval
from maya_meet.actions import MeetingActionRunner, meeting_action_class
from maya_meet.audio_wake import RecallAudioWakeState, timestamp_from_recall_payload
from maya_meet.engagement import decision_from_audio_wake, meet_address_decision, strip_maya_address
from maya_meet.output_media import MeetOutputQueue
from maya_meet.policy import meeting_turn_decision
from maya_voice.voice import VoiceNode


PRIVATE_TERMS = re.compile(
    r"\b("
    r"private|personal|memory|my\s+notes?|private\s+notes?|personal\s+notes?|logs?|files?|my\s+documents?|"
    r"password|passcode|pin|api\s*keys?|api\s*tokens?|access\s*tokens?|auth\s*tokens?|"
    r"tokens?|credentials?|secret(?:\s+keys?)?|bank|account\s+number"
    r")\b",
    re.IGNORECASE,
)

PRIVATE_ROOM_REFUSAL = "I can't read private material into the meeting room. I can keep that to your owner channel."
PERSONAL_CONTACT_RE = re.compile(
    r"\b(?:my\s+)?(?:phone|mobile|whatsapp|number|email|address)\b.{0,40}"
    r"(?:\+?\d[\d\s().-]{6,}\d|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})",
    re.IGNORECASE,
)


class MeetM1Responder:
    def __init__(
        self,
        *,
        db_path: str,
        output_queue: MeetOutputQueue,
        voice_node: VoiceNode | None = None,
        answerer=None,
        audio_wake_state: RecallAudioWakeState | None = None,
        action_runner: MeetingActionRunner | None = None,
        approval_sender: TelegramSender | None = None,
        m2_enabled: bool = False,
        provenance_resolver=None,
    ):
        self.db_path = db_path
        self.output_queue = output_queue
        self.voice_node = voice_node or VoiceNode(db_path=db_path)
        self.answerer = answerer
        self.audio_wake_state = audio_wake_state
        self.action_runner = action_runner
        self.approval_sender = approval_sender
        self.m2_enabled = bool(m2_enabled)
        self.provenance_resolver = provenance_resolver
        self.transcript_lines: deque[str] = deque(maxlen=60)
        self.meeting_context_lines: deque[str] = deque(maxlen=40)
        self.own_output_markers: deque[tuple[float, str]] = deque(maxlen=16)
        self.logger = logging.getLogger("maya.meet.responder")

    async def process_verified_event(self, payload: dict[str, Any]) -> dict[str, str]:
        text = extract_transcript_text(payload)
        if not text:
            return {"status": "ignored", "reason_code": "no_transcript_text"}
        if self._is_recent_self_output_echo(text):
            if self.audio_wake_state is not None:
                self.audio_wake_state.clear_pending_wake()
                self.audio_wake_state.suppress_for(2.0)
            return {"status": "ignored", "reason_code": "maya_self_output_echo"}
        self.transcript_lines.append(text)
        address = meet_address_decision(text)
        acoustic_match = None
        if not address.addressed and self.audio_wake_state is not None:
            acoustic_match = self.audio_wake_state.match_transcript(transcript_timestamp=timestamp_from_recall_payload(payload))
            if acoustic_match.matched:
                address = decision_from_audio_wake(
                    text,
                    confidence=acoustic_match.confidence,
                    delay_seconds=acoustic_match.delay_seconds,
                )
        prompt_text = address.remainder if address.addressed else text
        action_class = meeting_action_class(prompt_text)
        content_class = _meeting_content_class(text, action_class)
        if not address.addressed:
            # Unaddressed meeting speech is context. Addressed prompts and action requests
            # are kept out so Maya does not summarize her instructions as meeting facts.
            if action_class == "answer" and content_class == "meeting_public":
                self.meeting_context_lines.append(text)
        policy_text = f"Maya, {prompt_text}" if address.reason_code == "audio_wake_matched_transcript" else text
        provenance, voiceprint_verified = self._meeting_provenance(payload, text)
        decision = meeting_turn_decision(
            text=policy_text,
            provenance=provenance,
            action_class=action_class,
            content_class=content_class,
            m2_enabled=self.m2_enabled,
            voiceprint_verified=voiceprint_verified,
        )
        if decision.status == "ignored":
            return {
                "status": "ignored",
                "reason_code": address.reason_code if address.reason_code.startswith("not_addressed") else decision.reason_code,
                "address_confidence": f"{address.confidence:.3f}",
            }
        self.logger.info(
            "meet address decision status=%s reason=%s confidence=%.3f acoustic_delay=%s text=%r",
            address.status,
            address.reason_code,
            address.confidence,
            f"{acoustic_match.delay_seconds:.3f}" if acoustic_match and acoustic_match.matched else "",
            text[:160],
        )
        if decision.status == "allowed" and self.action_runner is not None:
            executed = await self.action_runner.run(
                request=prompt_text,
                action_class=action_class,
                session_id=str(payload.get("maya_session_id") or payload.get("session_id") or ""),
            )
            response = executed.spoken
        elif decision.status == "needs_confirmation":
            approval = await request_meeting_owner_approval(
                self.db_path,
                request=prompt_text,
                action_class=action_class,
                content_class=content_class,
                reason_code=decision.reason_code,
                session_id=str(payload.get("maya_session_id") or payload.get("session_id") or ""),
                telegram_sender=self.approval_sender,
            )
            response = approval.spoken
        else:
            response = await self._response_text(text, decision.status, decision.reason_code, prompt_text=prompt_text)
        if decision.status == "answer_allowed" and _contains_private_material(response):
            response = PRIVATE_ROOM_REFUSAL
        try:
            audio_path = await self.voice_node.render_audio_file(response)
            queued = await self.output_queue.queue_audio(
                audio_path,
                preview=response,
                session_id=str(payload.get("maya_session_id") or payload.get("session_id") or ""),
            )
        except Exception as exc:
            self.logger.exception("Meet Output Media response failed")
            return {"status": "failed", "reason_code": "output_media_failed", "detail": str(exc)[:200]}
        self._record_own_output(response)
        return {
            "status": "queued",
            "reason_code": "output_media_queued",
            "utterance_id": queued.utterance_id,
            "address_reason_code": address.reason_code,
            "address_confidence": f"{address.confidence:.3f}",
        }

    def _meeting_provenance(self, payload: dict[str, Any], text: str):
        if self.provenance_resolver is None:
            return provenance_from_source_channel("meeting_speech"), False
        resolved = self.provenance_resolver(payload, text)
        if isinstance(resolved, tuple) and len(resolved) == 2:
            return resolved
        return resolved, False

    async def _response_text(self, text: str, status: str, reason_code: str, *, prompt_text: str | None = None) -> str:
        if reason_code == "owner_private_disclosure_blocked":
            return PRIVATE_ROOM_REFUSAL
        if reason_code == "owner_private_disclosure_requires_telegram":
            return "That needs Zainal's Telegram approval before I can expose private material in the meeting."
        if reason_code == "meeting_room_audio_cannot_approve":
            return "Meeting audio can't approve actions. Zainal has to approve from Telegram."
        if status == "blocked":
            return "I can answer from the meeting context, but I can't take actions from the meeting in this mode."
        prompt = (prompt_text if prompt_text is not None else strip_maya_address(text)).lower()
        if "hear" in prompt:
            return "Yes, I can hear you in the meeting."
        if _asks_for_last_spoken(prompt):
            return self._last_spoken_text()
        if "summar" in prompt:
            return self._summary_text()
        if self.answerer is not None:
            try:
                answer = await self.answerer(strip_maya_address(text), list(self.meeting_context_lines))
                cleaned = " ".join(str(answer or "").split())
                if cleaned:
                    return cleaned[:500]
            except Exception:
                self.logger.exception("Meet context answerer failed")
        return "I'm listening. I can answer from the meeting context, but actions stay off in this meeting mode."

    def _summary_text(self) -> str:
        candidates = list(self.meeting_context_lines)
        if not candidates:
            return "I can hear the meeting, but I don't have enough meeting context to summarize yet."
        recent = " ".join(_room_safe_context_line(line) for line in candidates[-3:])
        return "The recent point was: " + recent[:220]

    def _last_spoken_text(self) -> str:
        candidates = list(self.meeting_context_lines)
        if not candidates:
            return "I can hear the meeting, but I don't have a prior meeting sentence to repeat yet."
        return "The last spoken sentence was: " + _room_safe_context_line(candidates[-1])[:220]

    def _record_own_output(self, response: str) -> None:
        normalized = _normalize_for_echo(response)
        if normalized:
            self.own_output_markers.append((time.time(), normalized))

    def _is_recent_self_output_echo(self, text: str) -> bool:
        normalized = _normalize_for_echo(text)
        if not normalized:
            return False
        now = time.time()
        while self.own_output_markers and now - self.own_output_markers[0][0] > 180:
            self.own_output_markers.popleft()
        for _, own in self.own_output_markers:
            if _same_or_contained(normalized, own):
                return True
            if SequenceMatcher(a=normalized, b=own).ratio() >= 0.78:
                return True
        return False


def extract_transcript_text(payload: dict[str, Any]) -> str:
    for key in ("text", "transcript", "utterance"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    data = payload.get("data")
    if isinstance(data, dict):
        nested = extract_transcript_text(data)
        if nested:
            return nested
    words = payload.get("words")
    if isinstance(words, list):
        parts = [str(item.get("text") or item.get("word") or "") for item in words if isinstance(item, dict)]
        return " ".join(part for part in parts if part).strip()
    return ""


def _asks_for_last_spoken(prompt: str) -> bool:
    lowered = prompt.lower()
    return (
        "last spoken" in lowered
        or "last sentence" in lowered
        or "last thing" in lowered
        or "what did" in lowered and "just" in lowered and "say" in lowered
    )


def _meeting_content_class(text: str, action_class: str) -> str:
    action = str(action_class or "").strip().lower()
    return "owner_private" if PRIVATE_TERMS.search(text) else "meeting_public"


def _contains_private_material(text: str) -> bool:
    value = str(text or "")
    return bool(PRIVATE_TERMS.search(value) or contains_sensitive_info(value) or PERSONAL_CONTACT_RE.search(value))


def _room_safe_context_line(text: str) -> str:
    value = str(text or "")
    if _contains_private_material(value):
        return "[sensitive details withheld]"
    return value


def _normalize_for_echo(text: str) -> str:
    lowered = str(text or "").lower()
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(lowered.split())


def _same_or_contained(candidate: str, own: str) -> bool:
    if candidate == own:
        return True
    if len(candidate) >= 24 and candidate in own:
        return True
    if len(own) >= 24 and own in candidate:
        return True
    candidate_tokens = set(candidate.split())
    own_tokens = set(own.split())
    if not candidate_tokens or not own_tokens:
        return False
    overlap = len(candidate_tokens & own_tokens) / max(1, len(candidate_tokens))
    return len(candidate_tokens) >= 5 and overlap >= 0.86
