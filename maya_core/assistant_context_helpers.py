from __future__ import annotations

from maya_core.assistant_command_helpers import direct_key
from maya_core.session_compactor import inspect_session_context


CONTEXT_KEYS = {
    "show context",
    "show context window",
    "show compacted context",
    "what is my context",
    "what context do you have",
    "what is the context window",
}


async def handle_context_command(db_path: str, text: str) -> str | None:
    if direct_key(text) not in CONTEXT_KEYS:
        return None
    return await inspect_session_context(db_path)
