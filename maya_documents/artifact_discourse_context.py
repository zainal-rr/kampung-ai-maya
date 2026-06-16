from __future__ import annotations

import re

from maya_documents.document_natural_artifact_parser import (
    clean_topic,
    clean_topic_part,
    normalize_artifact_command_text,
    strip_creation_prefix,
)
from storage import get_history


_REFERENCE_WORDS = {
    "this",
    "that",
    "it",
    "one",
    "thing",
    "topic",
    "answer",
    "response",
    "previous",
    "latest",
    "current",
    "above",
}


async def resolve_referenced_artifact_topic(
    db_path: str,
    channel: str,
    topic: str,
    current_text: str = "",
) -> str:
    if not is_referenced_topic(topic):
        return topic
    recent = await recent_conversation_artifact_topic(db_path, current_text=current_text)
    return recent or topic


async def recent_conversation_artifact_topic(db_path: str, current_text: str = "") -> str:
    try:
        history = await get_history(db_path, 1, limit=12)
    except Exception:
        return ""
    current_norm = _norm(current_text)
    user_candidates: list[str] = []
    assistant_candidates: list[str] = []
    for turn in reversed(history):
        content = str(turn.get("content") or "")
        if not content.strip():
            continue
        if current_norm and _norm(content) == current_norm:
            continue
        if turn.get("role") == "user":
            candidate = _topic_from_user_turn(content)
            if candidate:
                user_candidates.append(candidate)
        elif turn.get("role") == "assistant":
            candidate = _topic_from_assistant_turn(content)
            if candidate:
                assistant_candidates.append(candidate)
    return (user_candidates or assistant_candidates or [""])[0]


def is_referenced_topic(topic: str) -> bool:
    cleaned = normalize_artifact_command_text(topic).lower()
    words = re.findall(r"[a-z0-9]+", cleaned)
    if not words:
        return True
    if len(words) <= 4 and all(word in _REFERENCE_WORDS for word in words):
        return True
    if "for this" in cleaned or "about this" in cleaned or "from this" in cleaned:
        return True
    return False


def _topic_from_user_turn(text: str) -> str:
    cleaned = normalize_artifact_command_text(text)
    lowered = cleaned.lower()
    if lowered.startswith(("/", "yes", "yeah", "yup", "ok", "okay", "sure", "no ")):
        return ""
    if lowered.startswith(("what ", "why ", "how ", "where ", "explain ", "tell me ")):
        return ""
    if "remember " in lowered or "forget " in lowered:
        return ""
    stripped = strip_creation_prefix(cleaned) or cleaned
    topic = clean_topic_part(stripped)
    topic = _remove_artifact_type_filler(topic)
    if is_referenced_topic(topic):
        return ""
    return clean_topic(topic) if _useful(topic) else ""


def _topic_from_assistant_turn(text: str) -> str:
    first = str(text or "").strip().splitlines()[0] if str(text or "").strip() else ""
    if not first or first.lower().startswith(("i understand:", "done.", "last route:", "self heal check:")):
        return ""
    topic = clean_topic_part(first)
    return clean_topic(topic) if _useful(topic) else ""


def _remove_artifact_type_filler(topic: str) -> str:
    cleaned = re.sub(
        r"\b(?:word\s+document|word\s+doc|docx|excel\s+sheet|excel\s+workbook|"
        r"spreadsheet|powerpoint\s+slides|powerpoint\s+deck|powerpoint|slides|deck|document)\b",
        " ",
        str(topic),
        flags=re.IGNORECASE,
    )
    return clean_topic_part(cleaned)


def _useful(topic: str) -> bool:
    words = re.findall(r"[a-z0-9]+", topic.lower())
    if len(words) < 2:
        return False
    blocked = {"make", "create", "write", "draft", "prepare", "generate", "document", "file"}
    return not all(word in blocked for word in words)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())
