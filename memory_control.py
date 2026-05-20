from __future__ import annotations

import aiosqlite

from session_memory_store import list_session_summaries
from storage import list_preferences


async def forget_memory(db_path: str, query: str) -> str:
    cleaned = " ".join(query.strip().split())
    if not cleaned:
        return "Use /forget followed by the specific memory or preference to remove."
    if cleaned.lower() in {"all", "everything", "all memory", "my memory"}:
        return "I need a more specific memory target before forgetting anything."
    pattern = f"%{cleaned}%"
    async with aiosqlite.connect(db_path) as db:
        pref = await db.execute("DELETE FROM preferences WHERE key LIKE ? OR value LIKE ?", (pattern, pattern))
        lessons = await db.execute(
            "DELETE FROM lessons WHERE raw_text LIKE ? OR normalized_rule LIKE ?",
            (pattern, pattern),
        )
        summaries = await db.execute("DELETE FROM session_summaries WHERE summary LIKE ?", (pattern,))
        await db.commit()
    total = pref.rowcount + lessons.rowcount + summaries.rowcount
    if total <= 0:
        return f"Forget result:\n1) I could not find a saved memory matching: {cleaned}"
    return (
        "Forget result:\n"
        f"1) Removed {total} matching memory records.\n"
        f"a) preferences: {pref.rowcount}\n"
        f"b) lessons: {lessons.rowcount}\n"
        f"c) compacted context summaries: {summaries.rowcount}"
    )


async def memory_sources_text(db_path: str, query: str = "") -> str:
    query = query.strip().lower()
    preferences = await list_preferences(db_path, limit=8)
    lessons = await _list_lessons(db_path, query)
    summaries = await list_session_summaries(db_path, limit=2)
    lines = ["Memory sources:"]
    lines.extend(_preference_lines(preferences, query))
    lines.extend(_lesson_lines(lessons))
    lines.extend(_summary_lines(summaries))
    return "\n".join(lines) if len(lines) > 1 else "Memory sources:\n1) No visible memory found yet."


async def cleanup_stale_memory(db_path: str, keep_summaries: int = 5) -> str:
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
    return (
        "Memory cleanup:\n"
        f"1) Removed stale compacted summaries: {stale_summaries.rowcount}\n"
        f"2) Removed old pending lessons: {stale_pending.rowcount}\n"
        "3) Preferences and confirmed lessons were left intact."
    )


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


def _preference_lines(items: list[dict[str, str]], query: str) -> list[str]:
    visible = [item for item in items if "chat_id" not in item["key"].lower()]
    if query:
        visible = [item for item in visible if query in f"{item['key']} {item['value']}".lower()]
    return [
        f"1) Preference: {item['value']} | source: {item['source']} | confidence: high"
        for item in visible[:5]
    ]


def _lesson_lines(items: list[dict[str, str]]) -> list[str]:
    return [
        f"2) Lesson: {item['normalized_rule']} | source: {item['source']} | confidence: {item['confidence']}"
        for item in items[:5]
    ]


def _summary_lines(items: list[dict[str, str | int]]) -> list[str]:
    lines = []
    for item in items[:2]:
        preview = " ".join(str(item["summary"]).split())[:120]
        lines.append(f"3) Context summary: {preview} | source: {item['source']} | confidence: medium")
    return lines
