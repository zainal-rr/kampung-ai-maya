from __future__ import annotations

import re

from maya_core.storage import get_history


_COUNT_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


def recent_questions_requested(text: str, topic: str = "") -> bool:
    haystack = f"{text} {topic}".lower()
    return bool(re.search(r"\blast\s+(?:\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:question|questions|message|messages|prompts?)\b", haystack))


def requested_recent_question_count(text: str, topic: str = "", default: int = 5) -> int:
    haystack = f"{text} {topic}".lower()
    match = re.search(r"\blast\s+(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:question|questions|message|messages|prompts?)\b", haystack)
    if not match:
        return default
    raw = match.group(1)
    count = int(raw) if raw.isdigit() else _COUNT_WORDS.get(raw, default)
    return max(1, min(10, count))


async def recent_user_questions(db_path: str, count: int, user_id: int = 1) -> list[str]:
    history = await get_history(db_path, user_id, limit=max(20, count * 4))
    user_messages = [row["content"].strip() for row in history if row.get("role") == "user" and row.get("content", "").strip()]
    return user_messages[-count:]
