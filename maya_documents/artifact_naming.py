from __future__ import annotations

import re
from pathlib import Path

from maya_documents.office_files import safe_slug


DEFAULT_SLUG_LENGTH = 40


def named_artifact_path(folder: Path, topic: str, suffix: str, *, max_slug: int = DEFAULT_SLUG_LENGTH) -> Path:
    suffix = suffix if suffix.startswith(".") else f".{suffix}"
    base = short_artifact_stem(topic, suffix)
    return versioned_path(folder / f"{base}-v1{suffix}")


def short_artifact_stem(topic: str, suffix: str = "") -> str:
    cleaned = _remove_parameters(_filename_topic(topic))
    subject = _subject_word(cleaned)
    purpose = _purpose_words(cleaned, suffix)
    words = []
    for word in [*subject, *purpose]:
        if word and word not in words:
            words.append(word)
        if len(words) >= 3:
            break
    return safe_slug(" ".join(words) or "maya-work", max_length=40)


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


def _remove_parameters(text: str) -> str:
    cleaned = str(text or "")
    cleaned = re.sub(
        r"\b(?:for|with)?\s*(?:\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)\s*[- ]?\s*(?:day|days)\b",
        " ",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r"\b(?:for|with)?\s*(?:\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:people|persons?|travelers?|travellers?|pax|adults?|guests?)\b",
        " ",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r"\b(?:make|create|write|draft|prepare|generate|me|please|can you|could you|may i)\b", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\b(?:word|docx|document|doc|excel|xlsx|spreadsheet|sheet|powerpoint|pptx|presentation|slides?)\b", " ", cleaned, flags=re.I)
    return " ".join(cleaned.split()).strip()


def _subject_word(text: str) -> list[str]:
    lowered = text.lower()
    if re.search(r"\bshawarma\b", lowered) and re.search(r"\bnasi\s+lemak\b", lowered):
        return ["shawarma", "nasi", "lemak"]
    if re.search(r"\bmeraki\b", lowered):
        return ["router", "meraki"] if re.search(r"\brouter\b", lowered) else ["meraki"]
    known_subjects = (
        ("nasi lemak", ["nasi", "lemak"]),
        ("shawarma", ["shawarma"]),
        ("kampung ai", ["kampung", "ai"]),
        ("kuala lumpur", ["kuala", "lumpur"]),
        ("hong kong", ["hong", "kong"]),
        ("new york", ["new", "york"]),
        ("router", ["router"]),
        ("tokyo", ["tokyo"]),
        ("seoul", ["seoul"]),
        ("almaty", ["almaty"]),
        ("kazakhstan", ["kazakhstan"]),
        ("japan", ["japan"]),
        ("kyoto", ["kyoto"]),
        ("osaka", ["osaka"]),
        ("bangkok", ["bangkok"]),
        ("singapore", ["singapore"]),
        ("monthly", ["monthly"]),
        ("office", ["office"]),
        ("drone", ["drone"]),
    )
    for marker, words in known_subjects:
        if re.search(rf"\b{re.escape(marker)}\b", lowered):
            return words
    if any(word in lowered for word in ("recipe", "recipes", "ingredient", "ingredients")):
        return ["recipes"]
    tokens = [token for token in re.findall(r"[a-z0-9]+", lowered) if token not in _FILENAME_STOP_WORDS]
    return tokens[:1]


def _purpose_words(text: str, suffix: str) -> list[str]:
    lowered = text.lower()
    if "template" in lowered:
        if any(word in lowered for word in ("budget", "expense", "expenses", "cost", "spend", "spending")):
            return ["budget", "template"]
        return ["template"]
    if any(word in lowered for word in ("deck", "slides", "presentation")) or suffix.endswith("pptx"):
        return ["deck"]
    if any(word in lowered for word in ("app", "planner", "dashboard")) or suffix.endswith("html"):
        return ["app"]
    if suffix.endswith("docx") and any(word in lowered for word in ("itinerary", "food trip", "trip", "travel", "holiday", "vacation", "hiking")):
        return ["itinerary"]
    if suffix.endswith("docx") and any(word in lowered for word in ("recipe", "recipes", "ingredient", "ingredients")):
        return ["recipes"]
    if suffix.endswith("xlsx") and any(word in lowered for word in ("budget", "expense", "expenses", "cost", "spend", "spending")):
        return ["budget", "tracker"]
    if any(word in lowered for word in ("config", "configuration")):
        return ["config"]
    if any(word in lowered for word in ("budget", "expense", "expenses", "cost", "spend", "spending")):
        return ["budget", "tracker"] if "tracker" in lowered or suffix.endswith("xlsx") else ["budget"]
    if "proposal" in lowered:
        return ["proposal"]
    if "itinerary" in lowered:
        return ["itinerary"]
    if any(word in lowered for word in ("food trip", "trip", "travel", "holiday", "vacation")):
        return ["itinerary"]
    if "setup" in lowered:
        return ["setup"]
    if "guide" in lowered:
        return ["guide"]
    if suffix.endswith("xlsx"):
        return ["tracker"]
    if suffix.endswith("docx"):
        return ["document"]
    return []


_FILENAME_STOP_WORDS = {
    "a", "an", "the", "for", "to", "in", "on", "about", "of", "with", "and", "or", "my", "our", "all", "both",
    "file", "real", "editable", "proper", "complete", "short", "quick", "simple",
}


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
