from __future__ import annotations

import aiosqlite


async def mark_canonical_used(db_path: str, memory_ids: list[str]) -> None:
    if not memory_ids:
        return
    async with aiosqlite.connect(db_path) as db:
        for memory_id in memory_ids:
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
