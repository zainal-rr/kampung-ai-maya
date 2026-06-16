from __future__ import annotations

from maya_core.response_policy import ResponsePolicy


TOPIC_CONTEXT_LIMIT = 6


def recent_topic_history(history: list[dict[str, str]]) -> list[dict[str, str]]:
    recent = []
    for item in reversed(history):
        if item.get("role") == "user" and ResponsePolicy.is_topic_break(item.get("content", "")):
            break
        recent.append(item)
        if len(recent) >= TOPIC_CONTEXT_LIMIT:
            break
    recent.reverse()
    return recent


def format_topic_context(history: list[dict[str, str]]) -> str:
    lines = []
    for item in history:
        role = item.get("role", "user").capitalize()
        content = item.get("content", "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)
