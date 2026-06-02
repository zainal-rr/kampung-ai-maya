from __future__ import annotations

import re

from voice_session_log import (
    export_latest_voice_session,
    format_last_voice_session,
    format_today_voice_sessions,
    format_voice_session_diagnostics,
    format_voice_session_search,
)


async def handle_voice_session_command(db_path: str, text: str) -> str | None:
    cleaned = " ".join(text.strip().split())
    lowered = cleaned.lower().rstrip("?.! ")
    if lowered in {
        "show last voice session",
        "show my last voice session",
        "review last voice session",
        "review my last voice session",
        "show last imac voice session",
        "show my last imac voice session",
    }:
        return await format_last_voice_session(db_path)
    if lowered in {
        "show today voice sessions",
        "show todays voice sessions",
        "list today voice sessions",
        "list todays voice sessions",
        "show today imac voice sessions",
    }:
        return await format_today_voice_sessions(db_path)
    if lowered in {
        "export last voice session",
        "export my last voice session",
        "export last imac voice session",
    }:
        return await export_latest_voice_session(db_path)
    if lowered in {
        "show voice session diagnostics",
        "show imac voice diagnostics",
        "show last voice diagnostics",
        "show last voice session diagnostics",
    }:
        return await format_voice_session_diagnostics(db_path)
    match = re.match(r"^(?:search voice sessions?|search imac voice sessions?)\s+(?:for\s+)?(.+)$", cleaned, re.I)
    if match:
        return await format_voice_session_search(db_path, match.group(1).strip())
    return None
