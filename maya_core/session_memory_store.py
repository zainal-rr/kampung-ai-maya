from __future__ import annotations

import aiosqlite


async def init_session_memory_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS session_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scope TEXT DEFAULT 'shared',
                summary TEXT NOT NULL,
                source TEXT DEFAULT 'no_key_compactor',
                message_count INTEGER DEFAULT 0,
                token_count INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await _ensure_column(db, "session_summaries", "token_count", "INTEGER DEFAULT 0")
        await _ensure_column(db, "session_summaries", "untrusted_influence", "INTEGER DEFAULT 0")
        await _ensure_column(db, "session_summaries", "injection_detected", "INTEGER DEFAULT 0")
        await db.commit()


async def save_session_summary(
    db_path: str,
    summary: str,
    *,
    scope: str = "shared",
    source: str = "no_key_compactor",
    message_count: int = 0,
    token_count: int = 0,
    untrusted_influence: bool = False,
    injection_detected: bool = False,
) -> int:
    await init_session_memory_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            INSERT INTO session_summaries (
                scope, summary, source, message_count, token_count,
                untrusted_influence, injection_detected, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                scope,
                summary,
                source,
                message_count,
                token_count,
                int(untrusted_influence),
                int(injection_detected),
            ),
        )
        await db.commit()
        return int(cursor.lastrowid)


async def latest_session_summary(db_path: str, scope: str = "shared") -> dict[str, str | int] | None:
    await init_session_memory_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT
                id, scope, summary, source, message_count, token_count,
                untrusted_influence, injection_detected, created_at, updated_at
            FROM session_summaries
            WHERE scope = ?
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (scope,),
        )
        row = await cursor.fetchone()
    return dict(row) if row else None


async def list_session_summaries(
    db_path: str,
    *,
    scope: str = "shared",
    limit: int = 3,
) -> list[dict[str, str | int]]:
    await init_session_memory_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT
                id, scope, summary, source, message_count, token_count,
                untrusted_influence, injection_detected, created_at, updated_at
            FROM session_summaries
            WHERE scope = ?
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (scope, limit),
        )
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def _ensure_column(db: aiosqlite.Connection, table: str, column: str, definition: str) -> None:
    cursor = await db.execute(f"PRAGMA table_info({table})")
    rows = await cursor.fetchall()
    if any(row[1] == column for row in rows):
        return
    await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
