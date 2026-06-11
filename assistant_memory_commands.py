from __future__ import annotations

import re

from assistant_command_helpers import (
    empty_preference_memory_reply,
    filter_user_visible_memory,
    format_memory_reply,
    is_preference_query,
)
from memory_control import forget_memory
from memory_service import MemoryService
from session_search import format_session_search_results, search_sessions


async def handle_memory_forget(db_path: str, text: str) -> str | None:
    query = _natural_forget_query(text)
    if query is None:
        return None
    return await forget_memory(db_path, query)


async def handle_memory_lookup(memory: MemoryService, text: str) -> str | None:
    direct = re.match(r"^(?:what(?:'s| is)|do you know)\s+my\s+(.+?)\??$", text, re.I)
    if direct:
        query = f"my {direct.group(1).strip()}"
        snippets = filter_user_visible_memory(await memory.search_direct_fact(query, limit=3))
        return format_memory_reply(query, snippets, False) if snippets else "I don't have that saved yet."
    prefer = re.match(r"^what\s+(?:do|did)\s+i\s+prefer(?:\s+(.+?))?\??$", text, re.I)
    if prefer:
        query = " ".join(part for part in ("I prefer", prefer.group(1) or "") if part).strip()
        snippets = filter_user_visible_memory(await memory.search_direct_fact(query, limit=3))
        return format_memory_reply(query, snippets, False) if snippets else "I don't have that saved yet."

    match = re.match(r"^(?:what do you remember about|search memory for|show memory about)\s+(.+)$", text, re.I)
    if not match:
        return None
    query = match.group(1).strip()
    preference_query = is_preference_query(query)
    if preference_query:
        snippets = filter_user_visible_memory(await memory.search_preferences(query, limit=6))
        return format_memory_reply(query, snippets, True) if snippets else empty_preference_memory_reply(query)
    snippets = filter_user_visible_memory(await memory.search(query, limit=6))
    if snippets:
        return format_memory_reply(query, snippets, False)
    rows = await search_sessions(memory.db_path, query, limit=5)
    return format_session_search_results(query, rows) if rows else "I don't have that saved in memory yet."


def _natural_forget_query(text: str) -> str | None:
    normalized = " ".join(str(text).strip().split()).strip()
    if not normalized:
        return None
    lowered = normalized.lower().rstrip("?.! ")
    if lowered.startswith("/forget"):
        return _specific_forget_target(normalized[len("/forget"):])
    if lowered.startswith("don't forget") or lowered.startswith("do not forget"):
        return None
    if lowered.startswith("forget to "):
        return None

    command_match = re.match(
        r"^(?:forget|delete|remove|clear)\s+(?:that\s+)?(.+?)(?:\s+from\s+(?:your\s+)?memory)?$",
        normalized,
        re.I,
    )
    if command_match:
        return _specific_forget_target(command_match.group(1))

    memory_match = re.match(
        r"^(?:delete|remove|clear)\s+(?:the\s+)?(?:saved\s+)?(?:memory|preference|fact|saved fact)\s+(?:about|for|that)\s+(.+)$",
        normalized,
        re.I,
    )
    if memory_match:
        return _specific_forget_target(memory_match.group(1))
    return None


def _specific_forget_target(target: str) -> str | None:
    cleaned = " ".join(str(target).strip().split()).strip(" .?!")
    if cleaned.lower().startswith("that "):
        cleaned = cleaned[5:].strip()
    vague = {
        "",
        "it",
        "this",
        "that",
        "all",
        "everything",
        "all memory",
        "my memory",
        "your memory",
        "memory",
    }
    if cleaned.lower() in vague:
        return cleaned or None
    return cleaned
