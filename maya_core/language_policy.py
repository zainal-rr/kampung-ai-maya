from __future__ import annotations

import re


MALAY_MARKERS = {
    "apa", "atau", "awak", "bagitau", "bahasa", "berapa", "berita", "boleh",
    "buat", "cerita", "cuaca", "dah", "dalam", "dekat", "dengan", "dia",
    "hari", "ini", "je", "kan", "kat", "kau", "ke", "kenapa", "lah", "macam",
    "mana", "melayu", "nak", "ni", "pun", "saya", "tak", "tapi", "tolong",
    "tu", "untuk", "yang",
}


def language_instruction(text: str) -> str:
    if wants_malay_or_manglish(text) or uses_malay_or_manglish(text):
        return (
            "Language rule for this reply: the current user message is Malay or Manglish, "
            "or explicitly asks for Malay or Manglish. Reply in natural Malay or Manglish."
        )
    return (
        "Language rule for this reply: the current user message is English. Reply in English only. "
        "Do not use Malay or Manglish words unless quoting the user or explaining a Malay phrase."
    )


def uses_malay_or_manglish(text: str) -> bool:
    tokens = set(re.findall(r"\b[a-zA-Z']+\b", text.lower()))
    if tokens & MALAY_MARKERS:
        return True
    compact = text.lower()
    return any(phrase in compact for phrase in ("macam mana", "tak boleh", "nak buat", "boleh tak"))


def wants_malay_or_manglish(text: str) -> bool:
    lowered = text.lower()
    patterns = (
        "reply in malay", "reply in manglish", "speak in malay", "speak in manglish",
        "cakap melayu", "cakap malay", "cakap in malay", "cakap manglish",
        "cakap in manglish", "bahasa melayu", "in malay please", "in manglish please",
    )
    return any(pattern in lowered for pattern in patterns)


def is_language_topic(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in ("malay", "manglish", "melayu", "bahasa", "language"))
