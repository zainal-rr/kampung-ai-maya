from __future__ import annotations

import re

from assistant_command_helpers import (
    empty_preference_memory_reply,
    filter_user_visible_memory,
    format_memory_reply,
    is_preference_query,
)
from memory_service import MemoryService
from session_search import format_session_search_results, search_sessions


async def handle_memory_lookup(memory: MemoryService, text: str) -> str | None:
    direct = re.match(r"^(?:what(?:'s| is)|do you know)\s+my\s+(.+?)\??$", text, re.I)
    if direct:
        query = f"my {direct.group(1).strip()}"
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
