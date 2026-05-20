from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

import aiosqlite


def _tz() -> ZoneInfo:
    return ZoneInfo(os.getenv("KAMPUNG_TIMEZONE", "Asia/Kuala_Lumpur"))


def _routine_dict(row: aiosqlite.Row) -> dict[str, str | int | None]:
    return {
        "id": row["id"],
        "name": row["name"],
        "kind": row["kind"],
        "channel": row["channel"],
        "local_time": row["local_time"],
        "weekday": row["weekday"],
        "active": row["active"],
        "autonomy_mode": row["autonomy_mode"],
        "last_run_key": row["last_run_key"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


async def init_routine_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS routines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                kind TEXT NOT NULL,
                channel TEXT DEFAULT 'imac',
                local_time TEXT NOT NULL,
                weekday INTEGER,
                active INTEGER DEFAULT 1,
                autonomy_mode TEXT DEFAULT 'auto_safe',
                last_run_key TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(kind, channel)
            )
            """
        )
        await db.commit()


async def create_or_update_routine(
    db_path: str,
    *,
    name: str,
    kind: str,
    channel: str,
    local_time: str,
    weekday: int | None,
    autonomy_mode: str = "auto_safe",
) -> int:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO routines (name, kind, channel, local_time, weekday, active, autonomy_mode, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(kind, channel) DO UPDATE SET
                name = excluded.name,
                local_time = excluded.local_time,
                weekday = excluded.weekday,
                active = 1,
                autonomy_mode = excluded.autonomy_mode,
                updated_at = CURRENT_TIMESTAMP
            """,
            (name, kind, channel, local_time, weekday, autonomy_mode),
        )
        cursor = await db.execute(
            "SELECT id FROM routines WHERE kind = ? AND channel = ?",
            (kind, channel),
        )
        row = await cursor.fetchone()
        await db.commit()
    return int(row[0])


async def list_routines(
    db_path: str,
    *,
    active_only: bool = True,
    limit: int = 20,
) -> list[dict[str, str | int | None]]:
    clause = "WHERE active = 1" if active_only else ""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""
            SELECT id, name, kind, channel, local_time, weekday, active, autonomy_mode,
                   last_run_key, created_at, updated_at
            FROM routines
            {clause}
            ORDER BY channel ASC, weekday IS NOT NULL, local_time ASC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
    return [_routine_dict(row) for row in rows]


async def deactivate_routine(db_path: str, *, kind: str, channel: str) -> bool:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            UPDATE routines
            SET active = 0, updated_at = CURRENT_TIMESTAMP
            WHERE kind = ? AND channel = ? AND active = 1
            """,
            (kind, channel),
        )
        await db.commit()
    return cursor.rowcount > 0


async def claim_due_routines(db_path: str, now_local: datetime | None = None) -> list[dict[str, str | int | None]]:
    current = now_local or datetime.now(_tz())
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, name, kind, channel, local_time, weekday, active, autonomy_mode,
                   last_run_key, created_at, updated_at
            FROM routines
            WHERE active = 1
            ORDER BY channel ASC, weekday IS NOT NULL, local_time ASC
            """
        )
        rows = await cursor.fetchall()

        due_rows = []
        for row in rows:
            if not _is_due(row, current):
                continue
            run_key = _run_key(row, current)
            await db.execute(
                """
                UPDATE routines
                SET last_run_key = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (run_key, row["id"]),
            )
            due_rows.append(row)

        await db.commit()
    return [_routine_dict(row) for row in due_rows]


def _is_due(row: aiosqlite.Row, current: datetime) -> bool:
    weekday = row["weekday"]
    if weekday is not None and int(weekday) != current.weekday():
        return False

    hour, minute = _parse_local_time(str(row["local_time"]))
    scheduled = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if current < scheduled:
        return False
    return str(row["last_run_key"] or "") != _run_key(row, current)


def _run_key(row: aiosqlite.Row, current: datetime) -> str:
    if row["weekday"] is None:
        return current.date().isoformat()
    iso = current.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _parse_local_time(raw: str) -> tuple[int, int]:
    hour_text, minute_text = raw.split(":", 1)
    return int(hour_text), int(minute_text)
