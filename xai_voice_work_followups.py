from __future__ import annotations

import os

from xai_realtime_tools import BROWSER_TOOL_NAME, MAYA_WORK_TOOL_NAME
from xai_voice_supervisor import SupervisedVoiceWork, classify_supervised_voice_work


def supervised_browser_request(transcript: str) -> str:
    work = supervised_voice_work(transcript)
    return work.request if work and work.tool_name == BROWSER_TOOL_NAME else ""


def supervised_voice_work(transcript: str) -> SupervisedVoiceWork | None:
    return classify_supervised_voice_work(transcript, browser_tool_name=BROWSER_TOOL_NAME, work_tool_name=MAYA_WORK_TOOL_NAME)


def looks_like_browser_status_question(lowered: str) -> bool:
    return any(marker in lowered for marker in ("what are you doing", "what did you do", "what happened", "show the request", "pull up the request", "status", "how will you search", "who will be doing"))


def auto_cancel_seconds() -> float:
    raw = os.getenv("XAI_VOICE_SUPERVISOR_AUTO_CANCEL_SECONDS", "2.0")
    try:
        value = float(raw)
    except ValueError:
        value = 2.0
    return max(0.0, min(value, 10.0))


def context_grace_seconds(kind: str) -> float:
    env_name = "XAI_VOICE_WORK_CONTEXT_GRACE_SECONDS"
    default = 1.0 if kind.startswith("browser") else 4.0
    if kind == "document":
        env_name = "XAI_VOICE_DOCUMENT_CONTEXT_GRACE_SECONDS"
        default = 8.0
    raw = os.getenv(env_name, str(default))
    try:
        value = float(raw)
    except ValueError:
        value = default
    return max(0.0, min(value, 12.0))


def extract_followup_context(transcript: str) -> str:
    cleaned = " ".join(transcript.strip().split())
    if not cleaned:
        return ""
    lowered = cleaned.lower()
    noise_markers = (
        "can you hear me",
        "hello maya",
        "hey maya",
        "maya?",
    )
    if any(marker in lowered for marker in noise_markers):
        parts = []
        for part in cleaned.replace("?", ".").split("."):
            lowered_part = part.lower().strip()
            if lowered_part and not any(marker.rstrip("?") in lowered_part for marker in noise_markers):
                parts.append(part.strip())
        cleaned = ". ".join(parts).strip()
    return cleaned


def looks_like_work_followup(text: str, kind: str) -> bool:
    lowered = text.lower().strip()
    if not lowered:
        return False
    if looks_like_voice_status_question(lowered):
        return False
    classified = classify_supervised_voice_work(lowered, browser_tool_name=BROWSER_TOOL_NAME, work_tool_name=MAYA_WORK_TOOL_NAME)
    if classified:
        if kind == "document" and looks_like_document_steer(lowered):
            return True
        return False
    general_markers = (
        "it's for ",
        "it’s for ",
        "it is for ",
        "for my ",
        "for our ",
        "for the ",
        "use ",
        "include ",
        "add ",
        "also ",
        "actually ",
        "i mean ",
        "what i mean",
        "make it ",
        "the document",
        "the file",
        "that one",
        "this one",
    )
    if any(marker in lowered for marker in general_markers):
        return True
    if kind == "document" and len(lowered.split()) <= 8:
        return lowered.startswith(("for ", "about ", "to "))
    return False


def looks_like_document_steer(lowered: str) -> bool:
    steer_markers = (
        "actually",
        "make it",
        "it's for",
        "it’s for",
        "it is for",
        "for my",
        "for our",
        "also include",
        "include",
        "add ",
        "change it",
        "update it",
        "use this",
        "rewrite",
    )
    content_markers = (
        "audience",
        "executive",
        "summary",
        "section",
        "slide",
        "column",
        "formula",
        "notes",
        "budget",
        "ed",
        "director",
        "boss",
        "team",
    )
    return any(marker in lowered for marker in steer_markers) or (
        lowered.startswith(("for ", "about ", "to ")) and any(marker in lowered for marker in content_markers)
    )


def artifact_type_for_request(request: str) -> str:
    lowered = request.lower()
    if any(term in lowered for term in ("powerpoint", "presentation", "slide", "slides", "pptx", "deck")):
        return "pptx"
    if any(term in lowered for term in ("excel", "spreadsheet", "workbook", "sheet", "budget", "xlsx")):
        return "xlsx"
    if any(term in lowered for term in ("word", "docx", "document", "doc file", "doc ")):
        return "docx"
    return ""


def request_with_followups(request: str, followups: list[str]) -> str:
    cleaned = " ".join(request.strip().split())
    unique_followups = []
    for followup in followups:
        item = " ".join(followup.strip().split())
        if item and item not in unique_followups:
            unique_followups.append(item)
    if not unique_followups:
        return cleaned
    return (
        f"{cleaned}\n\n"
        "Additional context Zainal gave while this work was starting:\n"
        + "\n".join(f"- {item}" for item in unique_followups)
    )


def looks_like_voice_status_question(lowered: str) -> bool:
    return any(
        marker in lowered
        for marker in (
            "what are you doing",
            "what are you working on",
            "what did you do",
            "what happened",
            "show the request",
            "pull up the request",
            "status",
            "is it ready",
            "are you done",
            "can you hear me",
            "hello maya",
        )
    )
