from __future__ import annotations

import os
import re
from dataclasses import dataclass

from language_policy import uses_malay_or_manglish, wants_malay_or_manglish


QUALITY_MARKERS = (
    "cerita", "karang", "manglish", "melayu", "bahasa", "natural",
    "gaya", "ayat", "wording", "preference", "remember", "ingat",
    "ajar", "teaching", "explain in malay", "jawab in manglish",
)
FILLERS = (
    "Jap, I tengok dulu.",
    "Okay, bagi I fikir kejap.",
    "Hmm, ni kena susun elok sikit.",
    "Sekejap, I jawab proper.",
)


@dataclass(frozen=True)
class ImacVoiceDecision:
    route: str
    reason: str
    filler: str = ""


def decide_imac_voice_route(text: str) -> ImacVoiceDecision:
    cleaned = " ".join(text.strip().split())
    if _explicit_complex(cleaned):
        return ImacVoiceDecision("assistant", "explicit complex cue")
    if _quality_sensitive(cleaned):
        return ImacVoiceDecision("gemini", "quality-sensitive Malay/Manglish", _filler(cleaned))
    if not _is_malay_or_manglish(cleaned):
        return ImacVoiceDecision("grok", "english or uncertain")
    word_count = len(re.findall(r"\b[\w']+\b", cleaned))
    threshold = int(os.getenv("IMAC_MALAY_GEMINI_MIN_WORDS", "12"))
    if word_count >= threshold:
        return ImacVoiceDecision("gemini", "long Malay/Manglish", _filler(cleaned))
    return ImacVoiceDecision("grok", "short Malay/Manglish")


def _is_malay_or_manglish(text: str) -> bool:
    return wants_malay_or_manglish(text) or uses_malay_or_manglish(text)


def _quality_sensitive(text: str) -> bool:
    lowered = text.lower()
    env_markers = tuple(
        marker.strip().lower()
        for marker in os.getenv("IMAC_MALAY_QUALITY_MARKERS", "").split(",")
        if marker.strip()
    )
    return any(marker in lowered for marker in QUALITY_MARKERS + env_markers)


def _explicit_complex(text: str) -> bool:
    lowered = text.lower()
    markers = (
        "this is complex", "this is a complex task", "this is a complex project",
        "route this to gpt", "route to gpt", "use gpt for this", "use gpt",
    )
    return any(marker in lowered for marker in markers)


def _filler(text: str) -> str:
    return FILLERS[sum(ord(ch) for ch in text) % len(FILLERS)]
