from __future__ import annotations

import re
from pathlib import Path

from office_files import safe_slug


DEFAULT_SLUG_LENGTH = 40


def named_artifact_path(folder: Path, topic: str, suffix: str, *, max_slug: int = DEFAULT_SLUG_LENGTH) -> Path:
    suffix = suffix if suffix.startswith(".") else f".{suffix}"
    base = safe_slug(_filename_topic(topic), max_length=max_slug)
    return versioned_path(folder / f"{base}-v1{suffix}")


def _filename_topic(topic: str) -> str:
    cleaned = " ".join(str(topic).strip().split())
    cleaned = _strip_delivery_instructions(cleaned)
    cleaned = re.sub(r"^(?:a|an|the)\s+", "", cleaned, flags=re.I)
    cleaned = re.sub(r"^(?:of|about|on|for)\s+(?:a|an|the)?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(
        r"^(?:simple|quick|rough|starter|basic|editable|complete)\s+",
        "",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r"\b(?:please|for me)\b", " ", cleaned, flags=re.I)
    return " ".join(cleaned.split()) or "maya-work"


def _strip_delivery_instructions(text: str) -> str:
    cleaned = text
    cleaned = re.sub(
        r"(?:^|[.!?;]\s*)\b(?:include|with|containing|add)\s+"
        r"(?:itinerary|agenda|schedule|sections?|slides?|food\s+highlights?|budget\s+notes?|recommendations?|summary|notes?)\b.*$",
        " ",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r"(?:^|[.!?;]\s*)\b(?:it|this|the\s+(?:app|file|document|spreadsheet|deck|presentation))\s+"
        r"(?:should|must|needs?\s+to|can)\b.*$",
        " ",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r"(?:^|[.!?;]\s*)\b(?:save|export|send|attach|give)\s+"
        r"(?:it|this|the\s+(?:file|document|spreadsheet|deck|presentation|app))?\s*"
        r"(?:as|to|into)?\s*(?:a|an|the)?\s*"
        r"(?:real|actual|editable|proper)?\s*"
        r"(?:docx|word|xlsx|excel|pptx|powerpoint|html|file|document|spreadsheet|deck|presentation|app)\b.*$",
        " ",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r"\b(?:as|in)\s+(?:a|an|the)?\s*(?:real|actual|editable|proper)?\s*"
        r"(?:docx|word|xlsx|excel|pptx|powerpoint|html)\s+(?:file|document|spreadsheet|deck|presentation|app)?\b",
        " ",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r"\b(?:docx|xlsx|pptx|html)\s+(?:file|document|spreadsheet|deck|presentation|app)\b",
        " ",
        cleaned,
        flags=re.I,
    )
    return " ".join(cleaned.split())


def versioned_path(path: Path) -> Path:
    if not path.exists():
        return path
    base_stem = re.sub(r"-v\d+$", "", path.stem)
    for version in range(2, 1000):
        candidate = path.with_name(f"{base_stem}-v{version}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find a free versioned filename for {path.name}.")
