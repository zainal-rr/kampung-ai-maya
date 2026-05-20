from __future__ import annotations

import json

import aiosqlite


async def init_hardware_event_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS hardware_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                event_type TEXT DEFAULT '',
                payload_json TEXT DEFAULT '{}',
                status TEXT DEFAULT 'recorded',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


async def record_hardware_event(
    db_path: str,
    *,
    source: str,
    event_type: str,
    payload: dict,
    status: str = "recorded",
) -> None:
    await init_hardware_event_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO hardware_events (source, event_type, payload_json, status)
            VALUES (?, ?, ?, ?)
            """,
            (source, event_type, json.dumps(payload), status),
        )
        await db.commit()


async def latest_hardware_events(db_path: str, source: str, limit: int = 5) -> list[dict[str, str]]:
    await init_hardware_event_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT source, event_type, payload_json, status, created_at
            FROM hardware_events
            WHERE source = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (source, limit),
        )
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]
