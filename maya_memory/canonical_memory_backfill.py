from __future__ import annotations

import aiosqlite

from maya_memory.canonical_memory import init_canonical_memory_db, upsert_canonical_memory


async def backfill_canonical_memory(db_path: str) -> int:
    await init_canonical_memory_db(db_path)
    created = 0
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        pref_rows = await (await db.execute("SELECT key, value, source FROM preferences")).fetchall()
        lesson_rows = await (
            await db.execute("SELECT normalized_rule, lesson_type, scope, channel, confidence FROM lessons WHERE status = 'active'")
        ).fetchall()
    for row in pref_rows:
        if _internal_memory(str(row["key"]), str(row["value"])):
            continue
        await upsert_canonical_memory(
            db_path,
            raw_text=str(row["key"]),
            content=str(row["value"]),
            kind="preference",
            scope="global",
            source_channel=str(row["source"]),
            confidence="high",
        )
        created += 1
    for row in lesson_rows:
        await upsert_canonical_memory(
            db_path,
            raw_text=str(row["normalized_rule"]),
            content=str(row["normalized_rule"]),
            kind=str(row["lesson_type"] or "lesson"),
            scope=str(row["scope"] or "global"),
            source_channel=str(row["channel"]),
            confidence=str(row["confidence"] or "medium"),
        )
        created += 1
    return created


def _internal_memory(key: str, value: str) -> bool:
    lowered = f"{key} {value}".lower()
    return "chat_id" in lowered or "/desktop/maya/" in lowered or lowered.startswith("maya_")
