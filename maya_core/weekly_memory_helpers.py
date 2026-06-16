from __future__ import annotations

from datetime import datetime

import aiosqlite


INTERNAL_PREF_MARKERS = (
    "chat_id", "work_location", "screen", "eye", "session", "status",
    "route", "cost", "usage", "active_workflow", "pending_browser_click",
    "voice_replies",
)
INTERNAL_TASK_ACTIONS = {"create_skill_scaffold", "send_message"}
TOPIC_STOPWORDS = {
    "about", "after", "again", "also", "because", "before", "being", "could",
    "doing", "explain", "from", "have", "hello", "maya", "minute", "more",
    "please", "right", "should", "tell", "that", "there", "this", "what",
    "when", "where", "which", "with", "would", "your",
}


async def _fetch_all(
    db: aiosqlite.Connection,
    query: str,
    params: tuple[str, ...] = (),
) -> list[dict[str, str]]:
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


def _section(title: str, values: list[str]) -> list[str]:
    if not values:
        return [f"{title}: none."]
    joined = "; ".join(value[:110] for value in values if value)
    return [f"{title}: {joined}."]


def _canonical_memory_ids(data: dict[str, list[dict[str, str]]]) -> tuple[str, ...]:
    ids = [str(item["memory_id"]) for item in data.get("canonical", []) if item.get("memory_id")]
    return tuple(dict.fromkeys(ids))


def _internal_preference(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in INTERNAL_PREF_MARKERS)


def _topic_highlights(history: list[dict[str, str]], limit: int = 6) -> list[str]:
    user_turns = [item["content"] for item in history if item.get("role") == "user"]
    assistant_turns = [item["content"] for item in history if item.get("role") == "assistant"]
    scores: dict[str, int] = {}
    for phrase in _topic_phrases(user_turns):
        scores[phrase] = scores.get(phrase, 0) + 6
    for token in _topic_tokens(" ".join(user_turns)):
        scores[token] = scores.get(token, 0) + 3
    for token in _topic_tokens(" ".join(assistant_turns)):
        scores[token] = scores.get(token, 0) + 1
    highlights = []
    for token, _ in sorted(scores.items(), key=lambda item: (-item[1], item[0])):
        if any(token in existing or existing in token for existing in highlights):
            continue
        highlights.append(token)
        if len(highlights) >= limit:
            break
    return highlights


def _topic_phrases(turns: list[str]) -> set[str]:
    phrases = set()
    for turn in turns:
        tokens = list(_ordered_topic_tokens(turn))
        for left, right in zip(tokens, tokens[1:]):
            phrases.add(f"{left} {right}")
    return phrases


def _ordered_topic_tokens(text: str) -> list[str]:
    import re

    return [
        token
        for token in re.findall(r"\b[a-z][a-z0-9]{3,}\b", text.lower())
        if token not in TOPIC_STOPWORDS
    ]


def _topic_tokens(text: str) -> set[str]:
    return set(_ordered_topic_tokens(text))


def _week_key(current: datetime) -> str:
    iso = current.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"
