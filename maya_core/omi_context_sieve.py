from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Awaitable, Callable

from maya_memory.canonical_memory import upsert_canonical_memory
from maya_core.permission_policy import contains_sensitive_info, contains_sensitive_phrase_cue
from maya_core.storage import add_knowledge_chunk

OmiProvider = Callable[[str], Awaitable[str]]

NOISE_MARKERS = (
    "[silence]",
    "[music]",
    "[unintelligible]",
    "unknown speaker",
    "can you hear me",
    "testing testing",
)


@dataclass(frozen=True)
class OmiSieveDecision:
    accepted: bool
    status: str
    summary: str = ""
    kind: str = "ambient_context"
    scope: str = "omi"
    confidence: str = "low"
    reason: str = ""


async def sieve_omi_transcript(text: str, provider: OmiProvider | None = None) -> OmiSieveDecision:
    cleaned = clean_transcript(text)
    if is_omi_noise(cleaned):
        return OmiSieveDecision(False, "noise", reason="low-signal transcript")
    if contains_sensitive_info(cleaned) or contains_sensitive_phrase_cue(cleaned):
        return OmiSieveDecision(False, "blocked_sensitive", reason="sensitive content")
    if provider:
        decision = _parse_provider_decision(await provider(_omi_prompt(cleaned)))
        if decision.status != "provider_unusable":
            return decision
    summary = _heuristic_summary(cleaned)
    if not summary:
        return OmiSieveDecision(False, "no_value", reason="no durable context")
    return OmiSieveDecision(True, "accepted", summary=summary, confidence=_confidence(cleaned))


async def ingest_omi_decision(db_path: str, decision: OmiSieveDecision, *, source_ref: str = "") -> str | None:
    if not decision.accepted or not decision.summary:
        return None
    await add_knowledge_chunk(db_path, decision.summary, category="omi_transcript", tags="omi,ambient")
    return await upsert_canonical_memory(
        db_path,
        raw_text=decision.summary,
        content=f"Omi ambient context: {decision.summary}",
        kind=decision.kind,
        scope=decision.scope,
        source_channel="omi",
        confidence=decision.confidence,
        source_ref=source_ref,
        allow_resurrect=False,
    )


def clean_transcript(text: str) -> str:
    cleaned = re.sub(r"\b(?:um+|uh+|erm+|ah+)\b", " ", str(text), flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def is_omi_noise(text: str) -> bool:
    lowered = text.lower()
    if len(text.split()) < 6:
        return True
    return any(marker in lowered for marker in NOISE_MARKERS)


def _omi_prompt(text: str) -> str:
    return "\n".join((
        "Distill this Omi transcript for Maya memory.",
        "Return JSON only: {\"status\":\"accepted|no_value\",\"summary\":\"...\",\"confidence\":\"low|medium\"}.",
        "Accept only decisions, tasks, project context, user instructions, or durable facts.",
        "Reject small talk, background chatter, guesses, sensitive data, and personality claims from ambient speech.",
        f"Transcript: {text[:6000]}",
    ))


def _parse_provider_decision(raw: str) -> OmiSieveDecision:
    blob = _json_blob(raw)
    if not blob:
        return OmiSieveDecision(False, "provider_unusable")
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        return OmiSieveDecision(False, "provider_unusable")
    status = str(data.get("status", "")).strip().lower()
    if status in {"no_value", "reject", "rejected"}:
        return OmiSieveDecision(False, "no_value", reason="provider rejected")
    summary = clean_transcript(str(data.get("summary", "")))
    if status == "accepted" and summary:
        confidence = str(data.get("confidence", "low")).strip().lower()
        return OmiSieveDecision(True, "accepted", summary=summary, confidence=confidence if confidence in {"low", "medium"} else "low")
    return OmiSieveDecision(False, "provider_unusable")


def _json_blob(text: str) -> str:
    match = re.search(r"\{[\s\S]*\}", str(text).strip())
    return match.group(0) if match else ""


def _heuristic_summary(text: str) -> str:
    lowered = text.lower()
    value_markers = (
        "remember",
        "decided",
        "decision",
        "task",
        "todo",
        "follow up",
        "meeting",
        "project",
        "deadline",
        "document",
        "proposal",
    )
    if not any(marker in lowered for marker in value_markers):
        return ""
    return text[:500]


def _confidence(text: str) -> str:
    lowered = text.lower()
    if any(marker in lowered for marker in ("remember", "decided", "deadline", "follow up")):
        return "medium"
    return "low"
