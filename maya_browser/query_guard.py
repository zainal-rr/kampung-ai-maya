from __future__ import annotations

import re


_FILLER_WORDS = {
    "a", "an", "and", "can", "could", "find", "for", "google", "i", "image", "images",
    "me", "no", "of", "please", "say", "search", "the", "to", "uh", "um", "want", "you",
}


def browser_query_is_incomplete(query: str) -> bool:
    cleaned = " ".join(str(query or "").strip().split())
    if not cleaned:
        return True
    tokens = re.findall(r"[a-z0-9]+", cleaned.lower())
    meaningful = [token for token in tokens if token not in _FILLER_WORDS and len(token) > 1]
    return not meaningful


def browser_query_topic(text: str) -> str:
    cleaned = re.sub(r"[?!]+$", "", str(text or "")).strip()
    cleaned = re.sub(r"\b(?:please|for me|maya)\b", " ", cleaned, flags=re.I)
    return " ".join(cleaned.strip(" .").split())
