from __future__ import annotations

import re


RELATION_WORDS = (
    "fiancee",
    "fiancé",
    "fiance",
    "wife",
    "husband",
    "girlfriend",
    "boyfriend",
    "partner",
    "mother",
    "father",
    "sister",
    "brother",
    "friend",
    "boss",
    "colleague",
)


def normalize_user_perspective_memory(text: str) -> str:
    cleaned = " ".join(str(text).strip().split())
    if not cleaned:
        return cleaned
    lowered = cleaned.lower()
    if not any(word in lowered for word in RELATION_WORDS):
        return cleaned
    cleaned = re.sub(r"\bmy\s+fianc(?:e|ee|é)\b", "Zainal's fiancee", cleaned, flags=re.I)
    cleaned = re.sub(r"\bmy\s+wife\b", "Zainal's wife", cleaned, flags=re.I)
    cleaned = re.sub(r"\bmy\s+husband\b", "Zainal's husband", cleaned, flags=re.I)
    cleaned = re.sub(r"\bmy\s+girlfriend\b", "Zainal's girlfriend", cleaned, flags=re.I)
    cleaned = re.sub(r"\bmy\s+boyfriend\b", "Zainal's boyfriend", cleaned, flags=re.I)
    cleaned = re.sub(r"\bmy\s+partner\b", "Zainal's partner", cleaned, flags=re.I)
    cleaned = re.sub(r"\bmy\s+mother\b", "Zainal's mother", cleaned, flags=re.I)
    cleaned = re.sub(r"\bmy\s+father\b", "Zainal's father", cleaned, flags=re.I)
    cleaned = re.sub(r"\bmy\s+sister\b", "Zainal's sister", cleaned, flags=re.I)
    cleaned = re.sub(r"\bmy\s+brother\b", "Zainal's brother", cleaned, flags=re.I)
    cleaned = re.sub(r"\bmy\s+friend\b", "Zainal's friend", cleaned, flags=re.I)
    cleaned = re.sub(r"\bmy\s+boss\b", "Zainal's boss", cleaned, flags=re.I)
    cleaned = re.sub(r"\bmy\s+colleague\b", "Zainal's colleague", cleaned, flags=re.I)
    return cleaned
