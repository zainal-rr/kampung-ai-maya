from __future__ import annotations

import json

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
                canonical_memory_ids TEXT DEFAULT '[]',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS weekly_memory_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_key TEXT NOT NULL,
                trigger_source TEXT NOT NULL DEFAULT 'manual',
                status TEXT NOT NULL DEFAULT 'running',
                started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME,
                summary_source TEXT DEFAULT '',
                provider_calls INTEGER DEFAULT 0,
                canonical_saved INTEGER DEFAULT 0,
                canonical_rejected INTEGER DEFAULT 0,
                canonical_memory_ids TEXT DEFAULT '[]',
                error TEXT DEFAULT ''
            )
            """
        )
        try:
            await db.execute("ALTER TABLE weekly_summaries ADD COLUMN canonical_memory_ids TEXT DEFAULT '[]'")
        except aiosqlite.OperationalError:
            pass
        for statement in (
            "ALTER TABLE weekly_memory_runs ADD COLUMN summary_source TEXT DEFAULT ''",
            "ALTER TABLE weekly_memory_runs ADD COLUMN provider_calls INTEGER DEFAULT 0",
            "ALTER TABLE weekly_memory_runs ADD COLUMN canonical_saved INTEGER DEFAULT 0",
            "ALTER TABLE weekly_memory_runs ADD COLUMN canonical_rejected INTEGER DEFAULT 0",
            "ALTER TABLE weekly_memory_runs ADD COLUMN canonical_memory_ids TEXT DEFAULT '[]'",
            "ALTER TABLE weekly_memory_runs ADD COLUMN error TEXT DEFAULT ''",
        ):
            try:
                await db.execute(statement)
            except aiosqlite.OperationalError:
                pass
        await db.commit()


async def save_weekly_summary(
    db_path: str,
    *,
    run_key: str,
    summary: str,
    source: str = "dry_run",
    canonical_memory_ids: str = "[]",
) -> None:
    await init_weekly_memory_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO weekly_summaries (run_key, summary, source, canonical_memory_ids, created_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(run_key) DO UPDATE SET
                summary = excluded.summary,
                source = excluded.source,
                canonical_memory_ids = excluded.canonical_memory_ids,
                created_at = CURRENT_TIMESTAMP
            """,
            (run_key, summary, source, canonical_memory_ids),
        )
        await db.commit()


async def latest_weekly_summary(db_path: str) -> dict[str, str] | None:
    await init_weekly_memory_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT run_key, summary, source, canonical_memory_ids, created_at
            FROM weekly_summaries
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """
        )
        row = await cursor.fetchone()
    return dict(row) if row else None


async def start_weekly_memory_run(db_path: str, *, run_key: str, trigger_source: str) -> int:
    await init_weekly_memory_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            INSERT INTO weekly_memory_runs (run_key, trigger_source, status, started_at)
            VALUES (?, ?, 'running', CURRENT_TIMESTAMP)
            """,
            (run_key, trigger_source or "manual"),
        )
        await db.commit()
        return int(cursor.lastrowid)


async def finish_weekly_memory_run(
    db_path: str,
    *,
    run_id: int,
    status: str,
    summary_source: str = "",
    provider_calls: int = 0,
    canonical_saved: int = 0,
    canonical_rejected: int = 0,
    canonical_memory_ids: tuple[str, ...] = (),
    error: str = "",
) -> None:
    await init_weekly_memory_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            UPDATE weekly_memory_runs
            SET status = ?,
                completed_at = CURRENT_TIMESTAMP,
                summary_source = ?,
                provider_calls = ?,
                canonical_saved = ?,
                canonical_rejected = ?,
                canonical_memory_ids = ?,
                error = ?
            WHERE id = ?
            """,
            (
                status,
                summary_source,
                provider_calls,
                canonical_saved,
                canonical_rejected,
                json.dumps(list(canonical_memory_ids)),
                error[:1000],
                run_id,
            ),
        )
        await db.commit()


async def latest_weekly_memory_runs(db_path: str, limit: int = 5) -> list[dict[str, str]]:
    await init_weekly_memory_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, run_key, trigger_source, status, started_at, completed_at,
                   summary_source, provider_calls, canonical_saved,
                   canonical_rejected, canonical_memory_ids, error
            FROM weekly_memory_runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]
