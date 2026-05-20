from __future__ import annotations

import aiosqlite


async def init_weekly_memory_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS weekly_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_key TEXT NOT NULL UNIQUE,
                summary TEXT NOT NULL,
                source TEXT DEFAULT 'dry_run',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


async def save_weekly_summary(
    db_path: str,
    *,
    run_key: str,
    summary: str,
    source: str = "dry_run",
) -> None:
    await init_weekly_memory_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO weekly_summaries (run_key, summary, source, created_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(run_key) DO UPDATE SET
                summary = excluded.summary,
                source = excluded.source,
                created_at = CURRENT_TIMESTAMP
            """,
            (run_key, summary, source),
        )
        await db.commit()


async def latest_weekly_summary(db_path: str) -> dict[str, str] | None:
    await init_weekly_memory_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT run_key, summary, source, created_at
            FROM weekly_summaries
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """
        )
        row = await cursor.fetchone()
    return dict(row) if row else None
