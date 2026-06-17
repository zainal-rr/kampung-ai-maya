from __future__ import annotations

import aiosqlite

from maya_memory.canonical_memory_text import memory_tokens, subject_key_from_text
from maya_memory.memory_audit import record_memory_audit_event


async def forget_canonical_memory_impl(db_path: str, query: str) -> int:
    subject_key = subject_key_from_text(query)
    tokens = memory_tokens(subject_key or query)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT memory_id, subject_key, content
            FROM canonical_memory_items
            WHERE status IN ('active', 'superseded')
            """
        )
        rows = await cursor.fetchall()
        matches = _forget_matches(rows, subject_key, tokens)
        for row in matches:
            await db.execute(
                """
                UPDATE canonical_memory_items
                SET status = 'forgotten', updated_at = CURRENT_TIMESTAMP
                WHERE memory_id = ?
                """,
                (str(row["memory_id"]),),
            )
        await db.commit()
    for row in matches:
        await record_memory_audit_event(
            db_path,
            event_type="canonical_forget",
            memory_id=str(row["memory_id"]),
            subject_key=str(row["subject_key"]),
            status_before="active",
            status_after="forgotten",
            source_channel="memory_control",
            source_ref=query,
            content=str(row["content"]),
        )
    if matches:
        from maya_core.context_window import on_canonical_forget

        await on_canonical_forget(db_path)
    return len(matches)


def _forget_matches(rows: list[aiosqlite.Row], subject_key: str, tokens: set[str]) -> list[dict]:
    matches = []
    for row in rows:
        content = str(row["content"])
        if subject_key and row["subject_key"] == subject_key:
            matches.append(dict(row))
        elif tokens and tokens.issubset(memory_tokens(f"{row['subject_key']} {content}")):
            matches.append(dict(row))
    return matches
