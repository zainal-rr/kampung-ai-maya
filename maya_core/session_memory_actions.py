from __future__ import annotations

import re

import aiosqlite

from curated_memory import (
    CORE_SCOPE,
    PROFILE_SCOPE,
    add_curated_memory,
    curated_memory_status,
    scope_summary,
)
from permission_policy import contains_sensitive_info
from session_memory_store import save_session_summary
from session_search import format_session_search_results, index_session_message, search_sessions


async def handle_session_memory_command(db_path: str, text: str) -> str | None:
    cleaned = " ".join(text.strip().split())
    lowered = cleaned.lower()
    if lowered in {"show profile memory", "show zainal profile memory", "show zainal profile summary"}:
        return _show_scope(await scope_summary(db_path, PROFILE_SCOPE), "zainal_profile_summary")
    if lowered in {"show maya core memory", "show core memory"}:
        return _show_scope(await scope_summary(db_path, CORE_SCOPE), "maya_core_memory")
    match = re.match(r"^(?:search session|search sessions|search old sessions|search what i said about)\s+(.+)$", cleaned, re.I)
    if match:
        query = match.group(1).strip()
        return format_session_search_results(query, await search_sessions(db_path, query))
    match = re.match(r"^(?:what did i tell you about|what did we discuss about)\s+(.+)$", cleaned, re.I)
    if match:
        query = match.group(1).strip()
        return format_session_search_results(query, await search_sessions(db_path, query))
    if re.match(r"^what did i tell you (?:in voice|by voice|just now|today)", cleaned, re.I):
        query = " ".join(cleaned.split()[-4:])
        return format_session_search_results(query, await search_sessions(db_path, query))
    if lowered in {"save this conversation for memory", "summarize this session", "save this session for memory"}:
        return await save_recent_session_memory(db_path)
    return None


async def save_recent_session_memory(db_path: str, limit: int = 18) -> str:
    rows = await _recent_history(db_path, limit)
    if not rows:
        return "I do not have enough recent conversation to save yet."
    user_lines = [
        " ".join(row["content"].split())
        for row in rows
        if row["role"] == "user" and len(row["content"].strip()) > 4
    ]
    if not user_lines:
        return "I do not have enough useful user context to save yet."
    safe_lines = [line for line in user_lines[-6:] if not contains_sensitive_info(line)]
    if not safe_lines:
        return "I did not save this session because the useful parts look sensitive."
    summary = "\n".join(
        [
            "Normal Maya session memory",
            "1) Recent user context",
            *[f"{chr(97 + idx)}) {line[:180]}" for idx, line in enumerate(safe_lines[:5])],
            "2) Use",
            "a) Treat this as continuity support, not a hard rule.",
        ]
    )
    await save_session_summary(db_path, summary, source="manual_session_memory", message_count=len(rows))
    promoted = []
    for line in safe_lines:
        if _looks_durable(line):
            ok, message = await add_curated_memory(db_path, line, source="session_memory")
            if ok:
                promoted.append(message)
    extra = "\n2) Durable memory updates: " + str(len(promoted)) if promoted else "\n2) Durable memory updates: 0"
    return "Saved session memory.\n1) Recent session summary saved." + extra


async def save_voice_session_summary(db_path: str, transcripts: list[str]) -> None:
    safe = [line for line in transcripts if line.strip() and not contains_sensitive_info(line)]
    if not safe:
        return
    summary = "\n".join(
        [
            "iMac voice session memory",
            "1) User said",
            *[f"{chr(97 + idx)}) {line[:180]}" for idx, line in enumerate(safe[-5:])],
            "2) Use",
            "a) Treat this as voice continuity support.",
        ]
    )
    await save_session_summary(db_path, summary, source="imac_voice_session", message_count=len(safe))
    for line in safe:
        await index_session_message(db_path, "user", line, "imac_voice")
        if _looks_durable(line):
            await add_curated_memory(db_path, line, source="imac_voice_session")


async def memory_overview(db_path: str) -> str:
    return await curated_memory_status(db_path)


async def _recent_history(db_path: str, limit: int) -> list[dict[str, str]]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT role, content FROM history ORDER BY rowid DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
    return [dict(row) for row in reversed(rows)]


def _show_scope(data: dict[str, str | int], label: str) -> str:
    summary = str(data["summary"]).strip() or "No entries yet."
    return (
        f"{label}\n"
        f"1) Usage: {data['percent']} percent, {data['chars']}/{data['cap']} chars\n"
        f"2) Entries\n{summary}"
    )


def _looks_durable(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in (
            "remember",
            "i prefer",
            "my preference",
            "do not",
            "don't",
            "must",
            "should",
            "kampung ai",
            "maya",
            "testing",
        )
    )
