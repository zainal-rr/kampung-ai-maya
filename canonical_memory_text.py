from __future__ import annotations

import re

STOPWORDS = {"a", "an", "are", "is", "my", "the", "that", "this", "to", "for", "of", "me", "i"}
TOKEN_ALIASES = {"snacks": "snack"}
TEST_MARKERS = ("test", "tests", "regression", "smoke", "temporary")
# Whole-word match only: substring matching wrongly flagged durable memories
# containing words like "latest" (test) or "contemporary" (temporary).
_TEST_MARKER_RE = re.compile(r"\b(?:" + "|".join(TEST_MARKERS) + r")\b")


def subject_key_from_text(text: str) -> str:
    cleaned = " ".join(str(text).strip().rstrip(".?!").split()).lower()
    cleaned = re.sub(r"^(?:remember that|remember|save this memory[: ]*)\s+", "", cleaned)
    direct = re.match(r"^(?:what(?:'s| is)|do you know)\s+my\s+(.+)$", cleaned)
    if direct:
        cleaned = "my " + direct.group(1)
    prefer = re.match(r"^what\s+(?:do|did)\s+i\s+prefer(?:\s+(.+))?$", cleaned)
    if prefer:
        cleaned = "i prefer " + (prefer.group(1) or "")
    match = re.match(r"^(.+?)\s+(?:is|are|=)\s+.+$", cleaned)
    if match:
        cleaned = match.group(1)
    return "_".join(token for token in _ordered_memory_tokens(cleaned) if token)


def value_from_text(text: str) -> str:
    cleaned = " ".join(str(text).strip().rstrip(".?!").split())
    match = re.match(r"^.+?\s+(?:is|are|=)\s+(.+)$", cleaned, re.I)
    return match.group(1).strip() if match else cleaned


def memory_tokens(text: str) -> set[str]:
    return {
        TOKEN_ALIASES.get(token, token)
        for token in re.findall(r"[a-z0-9]+", str(text).lower())
        if len(token) > 1 and token not in STOPWORDS
    }


def is_temporary_memory(content: str, subject_key: str) -> bool:
    # Subject keys join tokens with underscores (a word character in regex),
    # so normalize separators to spaces before whole-word matching.
    haystack = re.sub(r"[^a-z0-9]+", " ", f"{subject_key} {content}".lower())
    return bool(_TEST_MARKER_RE.search(haystack))


def _ordered_memory_tokens(text: str) -> list[str]:
    return [
        TOKEN_ALIASES.get(token, token)
        for token in re.findall(r"[a-z0-9]+", str(text).lower())
        if len(token) > 1 and token not in STOPWORDS
    ]
