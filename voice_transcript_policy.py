from __future__ import annotations

import re


LONG_WORK_MARKERS = (
    "make me",
    "create",
    "draft",
    "write",
    "save",
    "word",
    "document",
    "file",
    "docx",
    "excel",
    "workbook",
    "xlsx",
    "spreadsheet",
    "budget tracker",
    "powerpoint",
    "pptx",
    "deck",
    "presentation",
    "browser",
    "open youtube",
    "search youtube",
    "research",
    "compare",
    "flight",
    "booking.com",
    "airbnb",
    "hotel",
    "complex",
    "self heal",
    "skill",
    "app building",
    "coding",
    "project",
)

SHORT_STATE_MARKERS = (
    "show route",
    "last route",
    "show status",
    "weekly status",
    "show cost",
    "show memory",
    "show review",
    "show delivery",
    "show providers",
    "what is my",
)

FILLER_WORDS = (
    "um",
    "uh",
    "erm",
    "hmm",
    "like",
    "you know",
    "actually",
    "basically",
    "okay so",
    "ok so",
)

TRAILING_CUTOFF_WORDS = {"with", "and", "or", "because", "then", "for", "to", "about"}


def should_park_voice_for_worker(transcript: str) -> bool:
    """True when live Grok voice should park work and let Maya workers handle it."""
    normalized = _normalize(transcript)
    if not normalized:
        return False
    if any(marker in normalized for marker in SHORT_STATE_MARKERS) and not _contains_artifact_or_tool_work(normalized):
        return False
    return _contains_artifact_or_tool_work(normalized)


def clean_voice_transcript_for_intent(transcript: str) -> str:
    """Lightly repair noisy voice transcripts before intent routing.

    The goal is not to rewrite meaning. It only removes common speech filler,
    explicit disturbance markers, and dangling cut-off connectives that break
    command/document parsers.
    """
    text = transcript.strip()
    if not text:
        return text
    text = re.sub(r"[\[(](?:background noise|noise|someone talking|connection broke|got cut off)[\])]", " ", text, flags=re.I)
    text = re.sub(r"\b(?:sorry,?\s*)?(?:start again|no wait|wait no|i mean)\b[:,]?", " ", text, flags=re.I)
    text = re.sub(r"\b(?:got cut off|line broke|background noise|someone talking)\b[:,]?", " ", text, flags=re.I)
    for filler in FILLER_WORDS:
        text = re.sub(rf"\b{re.escape(filler)}\b[:,]?", " ", text, flags=re.I)
    text = re.sub(r"\b(can you|could you)\s+\1\b", r"\1", text, flags=re.I)
    text = re.sub(r"^(?:can you|could you|would you|please)\s+", "", text.strip(), flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" ,")
    words = text.split()
    while words and words[-1].lower().strip(".,!?") in TRAILING_CUTOFF_WORDS:
        words.pop()
    return " ".join(words).strip() or transcript.strip()


def transcript_quality_notes(transcript: str) -> list[str]:
    normalized = transcript.lower()
    notes: list[str] = []
    if re.search(r"\b(um+|uh+|erm+|like|you know|actually|wait|sorry)\b", normalized):
        notes.append("filler")
    if re.search(r"\b(?:i mean|no wait|start again|sorry)\b", normalized):
        notes.append("self-correction")
    if transcript.rstrip().endswith(("...", "-", "—")) or re.search(r"\b(?:then|because|with|and)\s*$", normalized):
        notes.append("cutoff")
    if re.search(r"\b(?:background|noise|someone talking|got cut|line broke|connection)\b", normalized):
        notes.append("disturbance")
    return notes


def _contains_artifact_or_tool_work(normalized: str) -> bool:
    return any(marker in normalized for marker in LONG_WORK_MARKERS) or bool(
        re.search(r"\b(open|send|edit|update)\s+(?:the\s+)?(?:last|latest|current)?\s*(?:document|file|deck|workbook|pptx|docx|xlsx)\b", normalized)
    )


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())
