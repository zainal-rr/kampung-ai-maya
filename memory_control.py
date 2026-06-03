from __future__ import annotations

import aiosqlite
import re

from canonical_memory import forget_canonical_memory, search_relevant_canonical_memories
from curated_memory import curated_memory_status, forget_curated_memory
from memory_display import canonical_lines, lesson_lines, preference_lines, summary_lines
from retention_policy import run_retention_cleanup
from session_memory_store import list_session_summaries
from storage import list_preferences

async def forget_memory(db_path: str, query: str) -> str:
    cleaned = " ".join(query.strip().split())
    if not cleaned:
        return "Use /forget followed by the specific memory or preference to remove."
    if cleaned.lower() in {"all", "everything", "all memory", "my memory"}:
        return "I need a more specific memory target before forgetting anything."
    pattern = f"%{cleaned}%"
    canonical = await forget_canonical_memory(db_path, cleaned)
    fuzzy = await _forget_fuzzy_memory(db_path, cleaned)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        pref = await db.execute("DELETE FROM preferences WHERE key LIKE ? OR value LIKE ?", (pattern, pattern))
        lessons = await db.execute(
            "DELETE FROM lessons WHERE raw_text LIKE ? OR normalized_rule LIKE ?",
            (pattern, pattern),
        )
        try:
            summaries = await db.execute("DELETE FROM session_summaries WHERE summary LIKE ?", (pattern,))
            summaries_count = summaries.rowcount
        except aiosqlite.OperationalError:
            summaries_count = 0
        history_count = await _delete_history_context_like(db, pattern)
        try:
            search_count = await _delete_session_search_context_like(db, pattern)
        except aiosqlite.OperationalError:
            search_count = 0
        await db.commit()
    curated = await forget_curated_memory(db_path, cleaned)
    total = canonical + pref.rowcount + lessons.rowcount + summaries_count + history_count + search_count + curated + fuzzy
    if total <= 0:
        return f"Forget result:\n1) I could not find a saved memory matching: {cleaned}"
    counts = (
        f"a) canonical memory: {canonical}\n"
        f"b) preferences: {pref.rowcount}\n"
        f"c) lessons: {lessons.rowcount}\n"
        f"d) compacted context summaries: {summaries_count}\n"
        f"e) raw conversation turns: {history_count}\n"
        f"f) session search rows: {search_count}\n"
        f"g) curated memory: {curated}\n"
        f"h) fuzzy memory matches: {fuzzy}"
    )
    return f"Forget result:\n1) Removed {total} matching memory records.\n{counts}"

async def _forget_fuzzy_memory(db_path: str, query: str) -> int:
    tokens = _memory_tokens(query)
    if len(tokens) < 2:
        return 0
    deleted = 0
    curated_deleted = 0
    related_tokens: set[str] = set()
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        pref_rows = await (await db.execute("SELECT key, value FROM preferences")).fetchall()
        for row in pref_rows:
            text = f"{row['key']} {row['value']}"
            if _token_match(tokens, text):
                related_tokens |= _memory_tokens(text) - tokens
                result = await db.execute("DELETE FROM preferences WHERE key = ?", (row["key"],))
                deleted += result.rowcount
        lesson_rows = await (await db.execute("SELECT id, raw_text, normalized_rule FROM lessons")).fetchall()
        for row in lesson_rows:
            text = f"{row['raw_text']} {row['normalized_rule']}"
            if _token_match(tokens, text):
                related_tokens |= _memory_tokens(text) - tokens
                result = await db.execute("DELETE FROM lessons WHERE id = ?", (row["id"],))
                deleted += result.rowcount
        try:
            summary_rows = await (await db.execute("SELECT id, summary FROM session_summaries")).fetchall()
            for row in summary_rows:
                if _token_match(tokens, row["summary"]):
                    result = await db.execute("DELETE FROM session_summaries WHERE id = ?", (row["id"],))
                    deleted += result.rowcount
        except aiosqlite.OperationalError:
            pass
        try:
            fact_rows = await (await db.execute("SELECT id, fact FROM context_facts")).fetchall()
            for row in fact_rows:
                if _token_match(tokens, row["fact"]):
                    result = await db.execute("DELETE FROM context_facts WHERE id = ?", (row["id"],))
                    deleted += result.rowcount
            vibe_rows = await (await db.execute("SELECT id, vibe FROM context_vibes")).fetchall()
            for row in vibe_rows:
                if _token_match(tokens, row["vibe"]):
                    result = await db.execute("DELETE FROM context_vibes WHERE id = ?", (row["id"],))
                    deleted += result.rowcount
        except aiosqlite.OperationalError:
            pass
        try:
            curated_rows = await (await db.execute("SELECT id, scope, content, status FROM curated_memory_items")).fetchall()
            for row in curated_rows:
                text = f"{row['scope']} {row['content']}"
                if _token_match(tokens, text):
                    related_tokens |= _memory_tokens(text) - tokens
                    result = await db.execute("DELETE FROM curated_memory_items WHERE id = ?", (row["id"],))
                    curated_deleted += result.rowcount
        except aiosqlite.OperationalError:
            pass
        deleted += await _delete_fuzzy_history_context(db, tokens, related_tokens)
        try:
            deleted += await _delete_fuzzy_session_search_context(db, tokens, related_tokens)
        except aiosqlite.OperationalError:
            pass
        await db.commit()
    return deleted + curated_deleted

async def _delete_history_context_like(db: aiosqlite.Connection, pattern: str) -> int:
    rows = await (await db.execute("SELECT rowid, role, content FROM history ORDER BY rowid")).fetchall()
    ids = _matching_context_ids(rows, lambda row, _combined: _like_match(pattern, row["content"]))
    return await _delete_history_ids(db, ids)

async def _delete_session_search_context_like(db: aiosqlite.Connection, pattern: str) -> int:
    rows = await (await db.execute("SELECT rowid, role, content FROM session_search ORDER BY rowid")).fetchall()
    ids = _matching_context_ids(rows, lambda row, _combined: _like_match(pattern, row["content"]))
    return await _delete_session_search_ids(db, ids)

async def _delete_fuzzy_history_context(db: aiosqlite.Connection, tokens: set[str], related_tokens: set[str]) -> int:
    rows = await (await db.execute("SELECT rowid, role, content FROM history ORDER BY rowid")).fetchall()
    ids = _matching_context_ids(rows, lambda row, combined: _token_match(tokens, combined) or _orphan_answer_match(row, related_tokens))
    return await _delete_history_ids(db, ids)


async def _delete_fuzzy_session_search_context(db: aiosqlite.Connection, tokens: set[str], related_tokens: set[str]) -> int:
    rows = await (await db.execute("SELECT rowid, role, content FROM session_search ORDER BY rowid")).fetchall()
    ids = _matching_context_ids(rows, lambda row, combined: _token_match(tokens, combined) or _orphan_answer_match(row, related_tokens))
    return await _delete_session_search_ids(db, ids)


def _matching_context_ids(rows: list[aiosqlite.Row], matches) -> set[int]:
    ids: set[int] = set()
    for idx, row in enumerate(rows):
        prev_text = rows[idx - 1]["content"] if idx > 0 else ""
        next_text = rows[idx + 1]["content"] if idx + 1 < len(rows) else ""
        combined = f"{prev_text} {row['content']} {next_text}"
        if not matches(row, combined):
            continue
        rowid = int(row["rowid"])
        ids.add(rowid)
        if str(row["role"]) == "user" and idx + 1 < len(rows) and str(rows[idx + 1]["role"]) == "assistant":
            ids.add(int(rows[idx + 1]["rowid"]))
        if str(row["role"]) == "assistant" and idx > 0 and str(rows[idx - 1]["role"]) == "user":
            ids.add(int(rows[idx - 1]["rowid"]))
    return ids


async def _delete_history_ids(db: aiosqlite.Connection, rowids: set[int]) -> int:
    deleted = 0
    for rowid in sorted(rowids):
        result = await db.execute("DELETE FROM history WHERE rowid = ?", (rowid,))
        deleted += result.rowcount
    return deleted


async def _delete_session_search_ids(db: aiosqlite.Connection, rowids: set[int]) -> int:
    deleted = 0
    for rowid in sorted(rowids):
        result = await db.execute("DELETE FROM session_search WHERE rowid = ?", (rowid,))
        deleted += result.rowcount
    return deleted


def _like_match(pattern: str, candidate: str) -> bool:
    needle = pattern.strip("%").lower()
    return needle in str(candidate).lower()


def _orphan_answer_match(row: aiosqlite.Row, related_tokens: set[str]) -> bool:
    if str(row["role"]) != "assistant" or not related_tokens:
        return False
    content_tokens = _memory_tokens(row["content"])
    if not content_tokens.intersection(related_tokens):
        return False
    content = str(row["content"]).lower()
    if len(content_tokens) <= 8:
        return True
    return any(marker in content for marker in ("saved", "profile", "remember", "memory"))


def _memory_tokens(text: str) -> set[str]:
    stop = {"a", "an", "the", "is", "are", "am", "my", "me", "i", "that", "this", "to", "for", "of"}
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 1 and token not in stop}


def _token_match(query_tokens: set[str], candidate: str) -> bool:
    candidate_tokens = _memory_tokens(candidate)
    return query_tokens.issubset(candidate_tokens)


async def memory_sources_text(db_path: str, query: str = "") -> str:
    query = query.strip().lower()
    canonical = await search_relevant_canonical_memories(db_path, query, limit=5)
    preferences = await list_preferences(db_path, limit=8)
    lessons = await _list_lessons(db_path, query)
    summaries = await list_session_summaries(db_path, limit=2)
    lines = ["Memory sources:", await curated_memory_status(db_path)]
    lines.extend(canonical_lines(canonical))
    lines.extend(preference_lines(preferences, query))
    lines.extend(lesson_lines(lessons))
    lines.extend(summary_lines(summaries))
    return "\n".join(lines) if len(lines) > 1 else "Memory sources:\n1) No visible memory found yet."


async def cleanup_stale_memory(db_path: str, keep_summaries: int = 5) -> str:
    retention = await run_retention_cleanup(db_path)
    async with aiosqlite.connect(db_path) as db:
        stale_summaries = await db.execute(
            """
            DELETE FROM session_summaries
            WHERE id NOT IN (
                SELECT id FROM session_summaries ORDER BY updated_at DESC, id DESC LIMIT ?
            )
            """,
            (keep_summaries,),
        )
        stale_pending = await db.execute(
            "DELETE FROM pending_lessons WHERE created_at < datetime('now', '-14 days')"
        )
        await db.commit()
    return "\n".join((
        "Memory cleanup:",
        f"1) Removed stale compacted summaries: {stale_summaries.rowcount}",
        f"2) Removed old pending lessons: {stale_pending.rowcount}",
        "3) Preferences and confirmed lessons were left intact.",
        f"4) Retention marked projects/tasks: {retention['projects_marked']}/{retention['tasks_marked']}; deleted records: {retention['projects_deleted']}/{retention['tasks_deleted']}.",
    ))


async def _list_lessons(db_path: str, query: str) -> list[dict[str, str]]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        if query:
            pattern = f"%{query}%"
            cursor = await db.execute(
                """
                SELECT normalized_rule, source, confidence, channel, created_at
                FROM (
                    SELECT normalized_rule, trigger AS source, confidence, channel, created_at
                    FROM lessons
                    WHERE normalized_rule LIKE ? OR raw_text LIKE ?
                    ORDER BY created_at DESC
                    LIMIT 8
                )
                """,
                (pattern, pattern),
            )
        else:
            cursor = await db.execute(
                """
                SELECT normalized_rule, trigger AS source, confidence, channel, created_at
                FROM lessons
                ORDER BY created_at DESC
                LIMIT 8
                """
            )
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]
