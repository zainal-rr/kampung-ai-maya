from __future__ import annotations

import re

from maya_documents.document_natural_artifact_parser import artifact_intent_clarification
from maya_documents.document_request_parser import document_request


def telegram_greeting_reply(original_text: str, clean_text: str) -> str | None:
    if clean_text.strip():
        return None
    lowered = " ".join(str(original_text or "").lower().split()).strip(" .,!?")
    if re.fullmatch(r"(?:(?:hey|hi|hello|helo|hai)\s+)?maya", lowered):
        return "Hey, I’m here. What do you need?"
    return None


def telegram_short_followup_context(text: str, history: list[dict[str, str]]) -> str:
    lowered = " ".join(str(text or "").lower().split()).strip(" ?.!,")
    if lowered not in {
        "what do you mean",
        "what do you meanv",
        "what is that",
        "what was that",
        "huh",
        "why",
        "why tho",
        "but i didn't ask for it",
        "but i didnt ask for it",
    }:
        return ""
    for item in reversed(history):
        if item.get("role") == "assistant" and item.get("content", "").strip():
            return "Immediate previous assistant reply:\n" + item["content"].strip()
    return ""


def telegram_document_failure_reply(text: str) -> str:
    return (
        "I tried to route that as a file request, but the document tool failed before delivery. "
        "I have not sent a file from that message."
    )


def strong_artifact_request(text: str) -> bool:
    if document_request(text) is not None:
        return True
    return artifact_intent_clarification(text) is not None


def enforce_telegram_truth_contract(response: str, lane: str, reason: str, channel: str) -> str:
    if channel != "telegram":
        return response
    if "[file:" in response:
        return response
    if not _model_only_lane(lane, reason):
        return response
    if _claims_completed_file_work(response):
        return "I have not created or sent a file from that message. Tell me Word, Excel, or PowerPoint and I’ll do it properly."
    if _claims_memory_write(response):
        return "I have not saved that as memory from this message."
    if _claims_memory_delete(response):
        return "I have not changed memory from this message. Tell me exactly what to forget and I’ll use the memory delete path."
    return response


def _model_only_lane(lane: str, reason: str) -> bool:
    lowered = f"{lane} {reason}".lower()
    return any(marker in lowered for marker in ("gemini flash text", "grok text/news", "claude steward"))


def _claims_completed_file_work(response: str) -> bool:
    lowered = " ".join(str(response or "").lower().split())
    if not any(noun in lowered for noun in _ARTIFACT_NOUNS):
        return False
    return any(re.search(pattern, lowered) for pattern in _COMPLETED_FILE_PATTERNS)


def _claims_memory_write(response: str) -> bool:
    lowered = " ".join(str(response or "").lower().split())
    return any(re.search(pattern, lowered) for pattern in _MEMORY_WRITE_PATTERNS)


def _claims_memory_delete(response: str) -> bool:
    lowered = " ".join(str(response or "").lower().split())
    if not any(marker in lowered for marker in ("memory", "preference", "saved", "remembered", "forgot")):
        return False
    return any(re.search(pattern, lowered) for pattern in _MEMORY_DELETE_PATTERNS)


_ARTIFACT_NOUNS = (
    "document",
    "word",
    "docx",
    "excel",
    "sheet",
    "spreadsheet",
    "workbook",
    "powerpoint",
    "pptx",
    "slides",
    "deck",
    "file",
    "attachment",
)

_COMPLETED_FILE_PATTERNS = (
    r"\bi(?:'ve| have)?\s+(?:created|made|drafted|generated|prepared|saved|attached|sent|updated)\b",
    r"\bdone[.!,: ]",
    r"\bcreated\b",
    r"\bsaved\b",
    r"\battached\b",
    r"\bsent\b",
)

_MEMORY_WRITE_PATTERNS = (
    r"\bi(?:'ve| have)?\s+(?:saved|remembered|learned|noted)\b",
    r"\bi learned and saved\b",
    r"\bi(?:'ve| have)?\s+noted\b",
)

_MEMORY_DELETE_PATTERNS = (
    r"\bi(?:'ve| have)?\s+(?:cleared|deleted|removed|forgotten|forgot)\b",
    r"\bdone[.!,: ]\s*i(?:'ve| have)?\s+(?:cleared|deleted|removed|forgotten|forgot)\b",
    r"\b(?:cleared|deleted|removed)\s+(?:that|the|your|my)?\s*(?:memory|preference|saved fact)\b",
)
