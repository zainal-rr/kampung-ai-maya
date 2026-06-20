from __future__ import annotations

import aiosqlite

from maya_memory.memory_audit import record_memory_audit_event


async def mark_canonical_used(
    db_path: str,
    memory_ids: list[str],
    *,
    event_type: str = "activation",
    source_ref: str = "",
) -> None:
    if not memory_ids:
        return
    used_rows = []
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        for memory_id in memory_ids:
            cursor = await db.execute(
                """
                SELECT memory_id, subject_key, content, status, source_channel, source_ref
                FROM canonical_memory_items
                WHERE memory_id = ?
                """,
                (memory_id,),
            )
            row = await cursor.fetchone()
            if row:
                used_rows.append(dict(row))
            await db.execute(
                """
                UPDATE canonical_memory_items
                SET last_used_at = CURRENT_TIMESTAMP,
                    reinforcement_count = COALESCE(reinforcement_count, 0) + 1
                WHERE memory_id = ?
                """,
                (memory_id,),
            )
        await db.commit()
    for row in used_rows:
        await record_memory_audit_event(
            db_path,
            event_type=event_type,
            memory_id=str(row["memory_id"]),
            subject_key=str(row["subject_key"]),
            status_before=str(row["status"]),
            status_after=str(row["status"]),
            source_channel=str(row["source_channel"] or "canonical_memory"),
            source_ref=source_ref or str(row["source_ref"] or ""),
            content=str(row["content"] or ""),
        )
