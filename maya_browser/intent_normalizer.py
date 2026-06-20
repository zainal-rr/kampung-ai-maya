from __future__ import annotations

import re


_BROWSER_MARKERS = (
    "airbnb",
    "booking",
    "browser",
    "chrome",
    "flight",
    "flights",
    "gcp",
    "google",
    "hotel",
    "hotels",
    "image",
    "images",
    "reddit",
    "search",
    "youtube",
    "you tube",
)


def normalize_browser_request(text: str) -> str:
    """Conservatively repair voice transcripts before browser routing."""
    cleaned = _normalize_spacing(text)
    if not cleaned:
        return ""
    repaired = _repair_common_asr(cleaned)
    if not _looks_browser_shaped(repaired):
        return cleaned
    repaired = _strip_voice_scaffold(repaired)
    repaired = _trim_to_browser_command(repaired)
    repaired = _normalize_image_intent(repaired)
    repaired = _normalize_google_search_intent(repaired)
    return _normalize_spacing(repaired)


def _normalize_spacing(text: str) -> str:
    text = re.sub(r"[“”]", '"', str(text or ""))
    text = re.sub(r"[‘’]", "'", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ,.")


def _repair_common_asr(text: str) -> str:
    replacements = {
        r"\bgind\b": "find",
        r"\bgoggle\b": "google",
        r"\bgoogel\b": "google",
        r"\bgoogling\s+search\b": "google search",
        r"\bgoogle\s+say\b": "google search",
        r"\bgoogle\s+set\b": "google search",
        r"\byou\s+tube\b": "youtube",
    }
    repaired = text
    for pattern, value in replacements.items():
        repaired = re.sub(pattern, value, repaired, flags=re.I)
    return repaired


def _looks_browser_shaped(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _BROWSER_MARKERS)


def _strip_voice_scaffold(text: str) -> str:
    cleaned = text
    wrappers = (
        r"^(?:uh+|um+|erm+|hmm+|no|okay|ok|actually|so|well)[,\s]+",
        r"^(?:hey\s+maya|maya)[,\s]+",
        r"^(?:can|could|would)\s+you\s+",
        r"^(?:i\s+want\s+you\s+to|i\s+want\s+to|i\s+need\s+you\s+to|please)\s+",
        r"^(?:help\s+me\s+to|help\s+me)\s+",
    )
    previous = ""
    while previous != cleaned:
        previous = cleaned
        for wrapper in wrappers:
            cleaned = re.sub(wrapper, "", cleaned, flags=re.I).strip(" ,.")
    return cleaned


def _trim_to_browser_command(text: str) -> str:
    command = re.search(
        r"\b(?:google\s+(?:search|images?)|search\s+(?:a\s+)?google\s+image|"
        r"image\s+search|search\s+images?|find\s+(?:a\s+)?google\s+image|find\s+images?)\b",
        text,
        flags=re.I,
    )
    if not command or command.start() == 0:
        return text
    prefix = text[: command.start()]
    tokens = re.findall(r"[a-z0-9]+", prefix.lower())
    harmless = {
        "actually", "can", "could", "i", "maya", "need", "no", "okay", "please",
        "so", "to", "uh", "um", "want", "well", "would", "you",
    }
    if tokens and all(token in harmless for token in tokens):
        return text[command.start():]
    return text


def _normalize_image_intent(text: str) -> str:
    patterns = (
        r"^(?:find|search|google)\s+(?:a\s+)?google\s+images?\s+(?:for|of|about)?\s*(.*)$",
        r"^(?:find|search|look\s+for)\s+(?:a\s+)?images?\s+(?:for|of|about)?\s*(.*)$",
        r"^google\s+images?\s+(?:for|of|about)?\s*(.*)$",
    )
    for pattern in patterns:
        match = re.match(pattern, text, flags=re.I)
        if match:
            topic = _normalize_spacing(match.group(1))
            return f"google images {topic}".strip()
    return text


def _normalize_google_search_intent(text: str) -> str:
    lowered = text.lower()
    if "google search" in lowered:
        return re.sub(r"\bgoogle\s+search\b", "google search", text, count=1, flags=re.I)
    match = re.match(r"^google\s+(.+)$", text, flags=re.I)
    if match and not re.match(r"^(images?|cloud|chrome)\b", match.group(1), flags=re.I):
        return "google search " + _normalize_spacing(match.group(1))
    return text
