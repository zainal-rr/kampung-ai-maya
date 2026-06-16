from __future__ import annotations

import uuid

import aiosqlite

from maya_core.storage import delete_preference, get_preference, upsert_preference


VOICE_HANDOFF_KEY = "maya_voice_handoff_request"
VOICE_HANDOFF_TABLE = "voice_handoff_requests"


async def init_voice_handoff_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {VOICE_HANDOFF_TABLE} (
                id TEXT PRIMARY KEY,
                request TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'parked',
                source TEXT DEFAULT 'grok_voice',
                voice_session_id TEXT DEFAULT '',
                result TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


async def save_voice_handoff_request(
    db_path: str,
    request: str,
    *,
    source: str = "grok_voice",
    voice_session_id: str = "",
) -> str | None:
    cleaned = " ".join(request.strip().split())
    if not cleaned:
        return None
    await init_voice_handoff_db(db_path)
    handoff_id = f"vho_{uuid.uuid4().hex[:12]}"
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            f"""
            INSERT INTO {VOICE_HANDOFF_TABLE} (id, request, status, source, voice_session_id)
            VALUES (?, ?, 'parked', ?, ?)
            """,
            (handoff_id, cleaned, source, voice_session_id),
        )
        await db.commit()
    await upsert_preference(db_path, VOICE_HANDOFF_KEY, cleaned, source="voice_handoff")
    return handoff_id


async def pop_voice_handoff_request(db_path: str) -> str | None:
    row = await _claim_parked_handoff(db_path)
    if row:
        await _refresh_latest_preference(db_path)
        return str(row["request"])
    legacy = await get_preference(db_path, VOICE_HANDOFF_KEY)
    if legacy is not None:
        await delete_preference(db_path, VOICE_HANDOFF_KEY)
    return legacy


async def complete_voice_handoff_request(
    db_path: str,
    request: str,
    *,
    result: str = "",
    status: str = "completed",
) -> None:
    await init_voice_handoff_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            f"""
            UPDATE {VOICE_HANDOFF_TABLE}
            SET status = ?, result = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = (
                SELECT id FROM {VOICE_HANDOFF_TABLE}
                WHERE request = ? AND status = 'running'
                ORDER BY datetime(created_at) ASC
                LIMIT 1
            )
            """,
            (status, result[:1000], request),
        )
        await db.commit()


async def clear_voice_handoffs(db_path: str, *, reason: str = "cleared") -> None:
    await init_voice_handoff_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            f"""
            UPDATE {VOICE_HANDOFF_TABLE}
            SET status = 'cancelled', result = ?, updated_at = CURRENT_TIMESTAMP
            WHERE status IN ('parked', 'running')
            """,
            (reason[:1000],),
        )
        await db.commit()
    await delete_preference(db_path, VOICE_HANDOFF_KEY)


async def voice_handoff_status_summary(db_path: str) -> str:
    await init_voice_handoff_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            f"""
            SELECT status, COUNT(*)
            FROM {VOICE_HANDOFF_TABLE}
            GROUP BY status
            ORDER BY status
            """
        )
        rows = await cursor.fetchall()
    if not rows:
        return "No parked voice handoffs."
    return "; ".join(f"{status}: {count}" for status, count in rows)


async def _claim_parked_handoff(db_path: str) -> aiosqlite.Row | None:
    await init_voice_handoff_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""
            SELECT id, request
            FROM {VOICE_HANDOFF_TABLE}
            WHERE status = 'parked'
            ORDER BY datetime(created_at) ASC
            LIMIT 1
            """
        )
        row = await cursor.fetchone()
        if row:
            await db.execute(
                f"""
                UPDATE {VOICE_HANDOFF_TABLE}
                SET status = 'running', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (row["id"],),
            )
            await db.commit()
        return row


async def _refresh_latest_preference(db_path: str) -> None:
    await init_voice_handoff_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            f"""
            SELECT request
            FROM {VOICE_HANDOFF_TABLE}
            WHERE status = 'parked'
            ORDER BY datetime(created_at) ASC
            LIMIT 1
            """
        )
        row = await cursor.fetchone()
    if row:
        await upsert_preference(db_path, VOICE_HANDOFF_KEY, row[0], source="voice_handoff")
    else:
        await delete_preference(db_path, VOICE_HANDOFF_KEY)
