from __future__ import annotations

import json
import re

from maya_core.relayed_content_provenance import relayed_untrusted_source_kind
from maya_core.storage import get_preference, upsert_preference

REWRITE_KEY_PREFIX = "telegram_last_rewrite_candidate"
MAX_CANDIDATE_CHARS = 1600


def is_rewrite_followup(text: str) -> bool:
    lowered = " ".join(str(text).lower().split())
    markers = (
        "warmer",
        "less dramatic",
        "more professional",
        "more casual",
        "polite and short",
        "make it polite",
        "make it short",
        "still short",
        "subject line",
        "shorter",
        "more practical",
        "keep it short",
        "simple answer",
        "too long",
        "like maya",
        "not like a document",
        "ringkas",
        "ringkaskan",
    )
    return any(marker in lowered for marker in markers)


async def rewrite_context_prompt(db_path: str, channel: str, text: str) -> str:
    if channel != "telegram" or not is_rewrite_followup(text):
        return ""
    candidate = await latest_rewrite_candidate(db_path, channel)
    if not candidate:
        return "[rewrite-candidate]\nNo suitable previous draft is available. Ask what text to rewrite in one short line."
    return f"[rewrite-candidate]\nRewrite this previous draft only:\n{candidate}"


async def latest_rewrite_candidate(db_path: str, channel: str) -> str:
    raw = await get_preference(db_path, _key(channel))
    if not raw:
        return ""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw[:MAX_CANDIDATE_CHARS]
    return str(data.get("text") or "")[:MAX_CANDIDATE_CHARS]


async def remember_rewrite_candidate(db_path: str, channel: str, user_text: str, assistant_text: str) -> None:
    if channel != "telegram" or not is_rewritable_reply(assistant_text):
        return
    if relayed_untrusted_source_kind(user_text):
        return
    payload = {
        "user_text": user_text[:400],
        "text": assistant_text.strip()[:MAX_CANDIDATE_CHARS],
    }
    await upsert_preference(db_path, _key(channel), json.dumps(payload, ensure_ascii=False), source="rewrite_context")


def is_rewritable_reply(text: str) -> bool:
    cleaned = text.strip()
    if not cleaned:
        return False
    lowered = cleaned.lower()
    blocked_prefixes = (
        "last route:",
        "last artifact review:",
        "memory sources:",
        "forget result:",
        "weekly memory status:",
        "maya status:",
        "provider readiness:",
        "usage estimate,",
        "workflow:",
        "active workflow:",
        "i still have this workflow open",
        "memory self-heal",
        "self heal check:",
        "i can't expose sensitive",
        "i can’t expose sensitive",
        "deleting files needs confirmation",
        "i created a word draft",
        "done. i created",
        "done. i updated",
        "last document:",
    )
    if lowered.startswith(blocked_prefixes):
        return False
    blocked_contains = (
        "[file:",
        "/users/",
        "cost recorded:",
        "route:",
        "snapshot path",
        "rollback command",
        "telegram upload timed out",
    )
    if any(marker in lowered for marker in blocked_contains):
        return False
    if re.search(r"\b(password|api key|passport|credit card|debit card|otp|private key)\b", lowered):
        return False
    return len(cleaned) <= MAX_CANDIDATE_CHARS


def _key(channel: str) -> str:
    return f"{REWRITE_KEY_PREFIX}:{channel}"
