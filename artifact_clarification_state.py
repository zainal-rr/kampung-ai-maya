from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

from document_natural_artifact_parser import clean_topic, clean_topic_part, normalize_artifact_command_text, strip_creation_prefix
from artifact_discourse_context import resolve_referenced_artifact_topic
from storage import delete_preference, get_preference, upsert_preference


PENDING_PREFIX = "maya_pending_artifact_request:"
TTL = timedelta(minutes=30)


async def save_pending_artifact_request(db_path: str, channel: str, text: str) -> None:
    topic = pending_topic_from_request(text)
    topic = await resolve_referenced_artifact_topic(db_path, channel, topic, text)
    if not topic:
        return
    payload = {
        "topic": topic,
        "original_text": normalize_artifact_command_text(text),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await upsert_preference(db_path, _key(channel), json.dumps(payload, ensure_ascii=False), source="document")


async def consume_pending_artifact_request(db_path: str, channel: str, answer: str) -> tuple[str, str] | None:
    kind = artifact_kind_answer(answer)
    if not kind:
        return None
    raw = await get_preference(db_path, _key(channel))
    if not raw:
        return None
    await delete_preference(db_path, _key(channel))
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    created_at = _parse_dt(payload.get("created_at"))
    if created_at and datetime.now(timezone.utc) - created_at > TTL:
        return None
    topic = clean_topic(str(payload.get("topic") or ""))
    return (kind, topic) if topic else None


async def cleanup_expired_pending_artifact_request(db_path: str, channel: str) -> None:
    key = _key(channel)
    raw = await get_preference(db_path, key)
    if not raw:
        return
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        await delete_preference(db_path, key)
        return
    created_at = _parse_dt(payload.get("created_at"))
    if created_at and datetime.now(timezone.utc) - created_at <= TTL:
        return
    await delete_preference(db_path, key)


def pending_topic_from_request(text: str) -> str:
    cleaned = normalize_artifact_command_text(text)
    without_document = clean_topic_part(cleaned.replace("document", " "))
    stripped = strip_creation_prefix(without_document) or without_document
    return clean_topic(clean_topic_part(stripped))


def artifact_kind_answer(text: str) -> str:
    cleaned = normalize_artifact_command_text(text).lower()
    cleaned = cleaned.replace("file", "").strip(" .")
    cleaned = _strip_confirmation_prefix(cleaned)
    cleaned = _strip_answer_fillers(cleaned)
    word_answers = {"word", "word doc", "word document", "doc", "docx", "work document"}
    excel_answers = {"excel", "excel sheet", "excel workbook", "spreadsheet", "sheet", "xlsx", "workbook"}
    ppt_answers = {"powerpoint", "powerpoint slides", "powerpoint deck", "slides", "deck", "pptx", "presentation"}
    if cleaned in word_answers:
        return "docx"
    if cleaned in excel_answers:
        return "xlsx"
    if cleaned in ppt_answers:
        return "pptx"
    if _contains_only_artifact_answer(cleaned, word_answers):
        return "docx"
    if _contains_only_artifact_answer(cleaned, excel_answers):
        return "xlsx"
    if _contains_only_artifact_answer(cleaned, ppt_answers):
        return "pptx"
    return ""


def _strip_confirmation_prefix(text: str) -> str:
    cleaned = text.strip(" .,")
    prefixes = (
        "yes",
        "yeah",
        "yup",
        "sure",
        "ok",
        "okay",
        "correct",
        "confirm",
        "please",
        "make it",
        "create it as",
        "make that",
        "create that as",
    )
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if cleaned == prefix:
                return ""
            if cleaned.startswith(prefix + " ") or cleaned.startswith(prefix + ","):
                cleaned = cleaned[len(prefix) :].strip(" .,")
                changed = True
    return cleaned


def _strip_answer_fillers(text: str) -> str:
    filler = {
        "mean",
        "i mean",
        "maybe",
        "probably",
        "uh",
        "um",
        "erm",
        "hmm",
        "a",
        "an",
        "the",
    }
    words = [word for word in re.findall(r"[a-z0-9]+", text.lower()) if word not in filler]
    return " ".join(words)


def _contains_only_artifact_answer(text: str, answers: set[str]) -> bool:
    if not text:
        return False
    normalized = " ".join(re.findall(r"[a-z0-9]+", text.lower()))
    for answer in answers:
        answer_norm = " ".join(re.findall(r"[a-z0-9]+", answer.lower()))
        if normalized == answer_norm:
            return True
    return False


def _key(channel: str) -> str:
    return f"{PENDING_PREFIX}{channel}"


def _parse_dt(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
