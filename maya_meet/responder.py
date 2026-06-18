from __future__ import annotations

import logging
import re
from collections import deque
from typing import Any

from maya_core.provenance import provenance_from_source_channel
from maya_meet.engagement import strip_maya_address
from maya_meet.output_media import MeetOutputQueue
from maya_meet.policy import meeting_turn_decision
from maya_voice.voice import VoiceNode


PRIVATE_TERMS = re.compile(r"\b(private|secret|memory|notes?|logs?|files?|documents?)\b", re.IGNORECASE)
ACTION_TERMS = re.compile(
    r"\b(open|browse|browser|search|make|create|edit|revise|send|delete|export|upload|submit|book|pay|login)\b",
    re.IGNORECASE,
)


class MeetM1Responder:
    def __init__(self, *, db_path: str, output_queue: MeetOutputQueue, voice_node: VoiceNode | None = None):
        self.db_path = db_path
        self.output_queue = output_queue
        self.voice_node = voice_node or VoiceNode(db_path=db_path)
        self.transcript_lines: deque[str] = deque(maxlen=30)
        self.logger = logging.getLogger("maya.meet.responder")

    async def process_verified_event(self, payload: dict[str, Any]) -> dict[str, str]:
        text = extract_transcript_text(payload)
        if not text:
            return {"status": "ignored", "reason_code": "no_transcript_text"}
        self.transcript_lines.append(text)
        action_class = _m1_action_class(text)
        content_class = "owner_private" if PRIVATE_TERMS.search(text) else "meeting_public"
        decision = meeting_turn_decision(
            text=text,
            provenance=provenance_from_source_channel("meeting_speech"),
            action_class=action_class,
            content_class=content_class,
            m2_enabled=False,
        )
        if decision.status == "ignored":
            return {"status": "ignored", "reason_code": decision.reason_code}
        response = self._response_text(text, decision.status, decision.reason_code)
        try:
            audio_path = await self.voice_node.render_audio_file(response)
            queued = await self.output_queue.queue_audio(audio_path, preview=response)
        except Exception as exc:
            self.logger.exception("Meet Output Media response failed")
            return {"status": "failed", "reason_code": "output_media_failed", "detail": str(exc)[:200]}
        return {"status": "queued", "reason_code": "output_media_queued", "utterance_id": queued.utterance_id}

    def _response_text(self, text: str, status: str, reason_code: str) -> str:
        if reason_code == "owner_private_disclosure_blocked":
            return "I can't read private material into the meeting room. I can keep that to your owner channel."
        if status == "blocked":
            return "I can answer from the meeting context, but I can't take actions from the meeting in this mode."
        prompt = strip_maya_address(text).lower()
        if "hear" in prompt:
            return "Yes, I can hear you in the meeting."
        if "summar" in prompt:
            return self._summary_text()
        return "I'm listening. I can answer from the meeting context, but actions stay off in this meeting mode."

    def _summary_text(self) -> str:
        candidates = [line for line in self.transcript_lines if not line.lower().lstrip().startswith(("maya", "hey maya"))]
        if not candidates:
            return "I can hear the meeting, but I don't have enough meeting context to summarize yet."
        recent = " ".join(candidates[-3:])
        return "The recent point was: " + recent[:220]


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


def _m1_action_class(text: str) -> str:
    return "lookup" if ACTION_TERMS.search(strip_maya_address(text)) else "answer"
