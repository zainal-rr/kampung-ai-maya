from __future__ import annotations

import json
import time
from typing import Any

import aiosqlite

from maya_meet.models import ROOM_LEVEL_LOCKED


async def init_meet_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS meet_sessions (
                session_id TEXT PRIMARY KEY,
                bot_id TEXT DEFAULT '',
                meeting_url TEXT NOT NULL,
                status TEXT NOT NULL,
                room_authority_level TEXT NOT NULL,
                failure_reason TEXT DEFAULT '',
                output_media_status TEXT DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS meet_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                event_id TEXT DEFAULT '',
                event_type TEXT NOT NULL,
                source_kind TEXT NOT NULL,
                speaker_label TEXT DEFAULT '',
                payload_json TEXT NOT NULL,
                accepted INTEGER NOT NULL DEFAULT 1,
                duplicate INTEGER NOT NULL DEFAULT 0,
                reason_code TEXT DEFAULT '',
                created_at REAL NOT NULL
            )
            """
        )
        await _ensure_column(db, "meet_events", "event_id", "TEXT DEFAULT ''")
        await _ensure_column(db, "meet_events", "duplicate", "INTEGER NOT NULL DEFAULT 0")
        await db.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_meet_events_event_id
            ON meet_events(event_id)
            WHERE event_id != '' AND accepted = 1 AND duplicate = 0
            """
        )
        await db.commit()


async def create_meet_session(db_path: str, *, session_id: str, meeting_url: str) -> None:
    now = time.time()
    await init_meet_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO meet_sessions
            (session_id, meeting_url, status, room_authority_level, created_at, updated_at)
            VALUES (?, ?, 'created', ?, ?, ?)
            """,
            (session_id, meeting_url, ROOM_LEVEL_LOCKED, now, now),
        )
        await db.commit()


async def update_meet_session(db_path: str, session_id: str, **fields: str) -> None:
    if not fields:
        return
    allowed = {"bot_id", "status", "failure_reason", "output_media_status", "room_authority_level"}
    clean = {key: value for key, value in fields.items() if key in allowed}
    if not clean:
        return
    clean["updated_at"] = time.time()
    assignments = ", ".join(f"{key} = ?" for key in clean)
    await init_meet_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(f"UPDATE meet_sessions SET {assignments} WHERE session_id = ?", (*clean.values(), session_id))
        await db.commit()


async def record_meet_event(
    db_path: str,
    *,
    session_id: str,
    event_type: str,
    payload: dict[str, Any],
    event_id: str = "",
    source_kind: str = "other_speaker",
    speaker_label: str = "",
    accepted: bool = True,
    duplicate: bool = False,
    reason_code: str = "",
) -> bool:
    await init_meet_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        try:
            await _insert_meet_event(
                db,
                session_id=session_id,
                event_id=event_id,
                event_type=event_type,
                source_kind=source_kind,
                speaker_label=speaker_label,
                payload=payload,
                accepted=accepted,
                duplicate=duplicate,
                reason_code=reason_code,
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            if not event_id or not accepted or duplicate:
                raise
            await _insert_meet_event(
                db,
                session_id=session_id,
                event_id=event_id,
                event_type="recall_event_duplicate",
                source_kind=source_kind,
                speaker_label=speaker_label,
                payload={"event_id": event_id},
                accepted=False,
                duplicate=True,
                reason_code="duplicate_recall_event",
            )
            await db.commit()
            return False


async def meet_session(db_path: str, session_id: str) -> dict[str, Any] | None:
    await init_meet_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM meet_sessions WHERE session_id = ?", (session_id,))
        row = await cursor.fetchone()
    return dict(row) if row else None


async def _insert_meet_event(
    db: aiosqlite.Connection,
    *,
    session_id: str,
    event_id: str,
    event_type: str,
    source_kind: str,
    speaker_label: str,
    payload: dict[str, Any],
    accepted: bool,
    duplicate: bool,
    reason_code: str,
) -> None:
    await db.execute(
        """
        INSERT INTO meet_events
        (session_id, event_id, event_type, source_kind, speaker_label, payload_json, accepted, duplicate, reason_code, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            event_id,
            event_type,
            source_kind,
            speaker_label,
            json.dumps(payload, sort_keys=True),
            int(accepted),
            int(duplicate),
            reason_code,
            time.time(),
        ),
    )


async def _ensure_column(db: aiosqlite.Connection, table: str, column: str, definition: str) -> None:
    cursor = await db.execute(f"PRAGMA table_info({table})")
    rows = await cursor.fetchall()
    if any(row[1] == column for row in rows):
        return
    await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
