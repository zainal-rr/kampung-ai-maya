from __future__ import annotations

import json

import aiosqlite

from maya_core.permission_policy import contains_sensitive_info


MAX_TURN_CHARS = 4000


async def init_voice_session_log_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS voice_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                ended_at DATETIME,
                close_reason TEXT DEFAULT '',
                duration_seconds REAL DEFAULT 0,
                input_device TEXT DEFAULT '',
                output_device TEXT DEFAULT '',
                sample_rate INTEGER DEFAULT 0,
                model TEXT DEFAULT '',
                voice TEXT DEFAULT '',
                audio_error_count INTEGER DEFAULT 0,
                output_reset_count INTEGER DEFAULT 0,
                input_chunks_captured INTEGER DEFAULT 0,
                input_chunks_sent INTEGER DEFAULT 0,
                input_bytes_sent INTEGER DEFAULT 0,
                last_input_audio_at REAL DEFAULT 0,
                last_local_mic_rms REAL DEFAULT 0,
                peak_local_mic_rms REAL DEFAULT 0,
                peak_local_mic_rms_since_response REAL DEFAULT 0,
                peak_local_mic_rms_since_response_at REAL DEFAULT 0,
                last_xai_speech_started_at REAL DEFAULT 0,
                last_user_transcript_at REAL DEFAULT 0,
                last_response_done_at REAL DEFAULT 0,
                transcript_count INTEGER DEFAULT 0,
                export_path TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await _ensure_voice_session_columns(db)
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS voice_session_turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                event_type TEXT DEFAULT '',
                response_id TEXT DEFAULT '',
                tool_name TEXT DEFAULT '',
                interrupted INTEGER DEFAULT 0,
                latency_ms INTEGER,
                diagnostics TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


async def start_voice_session(
    db_path: str,
    *,
    input_device: str = "",
    output_device: str = "",
    sample_rate: int = 0,
    model: str = "",
    voice: str = "",
) -> int:
    await init_voice_session_log_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            INSERT INTO voice_sessions (
                input_device, output_device, sample_rate, model, voice
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (input_device, output_device, sample_rate, model, voice),
        )
        await db.commit()
        return int(cursor.lastrowid)


async def record_voice_turn(
    db_path: str,
    session_id: int | None,
    role: str,
    content: str,
    *,
    event_type: str = "",
    response_id: str = "",
    tool_name: str = "",
    interrupted: bool = False,
    latency_ms: int | None = None,
    diagnostics: dict | None = None,
) -> None:
    if not session_id:
        return
    cleaned = _clean_content(content)
    if not cleaned:
        return
    try:
        await init_voice_session_log_db(db_path)
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                """
                INSERT INTO voice_session_turns (
                    session_id, role, content, event_type, response_id, tool_name,
                    interrupted, latency_ms, diagnostics
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    role,
                    cleaned,
                    event_type,
                    response_id,
                    tool_name,
                    1 if interrupted else 0,
                    latency_ms,
                    json.dumps(diagnostics or {}, ensure_ascii=True),
                ),
            )
            await db.commit()
    except aiosqlite.Error:
        return


async def latest_voice_session(db_path: str) -> dict | None:
    await init_voice_session_log_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT *
            FROM voice_sessions
            ORDER BY started_at DESC, id DESC
            LIMIT 1
            """
        )
        row = await cursor.fetchone()
    return dict(row) if row else None


async def voice_session_turns(db_path: str, session_id: int, limit: int = 80) -> list[dict]:
    await init_voice_session_log_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT *
            FROM voice_session_turns
            WHERE session_id = ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (session_id, limit),
        )
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def list_today_voice_sessions(db_path: str, limit: int = 10) -> list[dict]:
    await init_voice_session_log_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT s.*,
                   (SELECT COUNT(*) FROM voice_session_turns t WHERE t.session_id = s.id) AS turn_count
            FROM voice_sessions s
            WHERE date(s.started_at, 'localtime') = date('now', 'localtime')
            ORDER BY s.started_at DESC, s.id DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def search_voice_sessions(db_path: str, query: str, limit: int = 8) -> list[dict]:
    cleaned = " ".join(query.strip().split())
    if not cleaned:
        return []
    await init_voice_session_log_db(db_path)
    terms = [term.replace('"', "") for term in cleaned.split() if len(term) > 2]
    like_exprs = [f"%{term}%" for term in terms] or [f"%{cleaned}%"]
    where = " AND ".join("t.content LIKE ?" for _ in like_exprs)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""
            SELECT t.*, s.started_at, s.close_reason
            FROM voice_session_turns t
            JOIN voice_sessions s ON s.id = t.session_id
            WHERE {where}
            ORDER BY t.created_at DESC, t.id DESC
            LIMIT ?
            """,
            (*like_exprs, limit),
        )
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def _voice_session_by_id(db_path: str, session_id: int) -> dict | None:
    await init_voice_session_log_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM voice_sessions WHERE id = ?", (session_id,))
        row = await cursor.fetchone()
    return dict(row) if row else None


def _clean_content(content: str) -> str:
    text = " ".join(str(content).split())
    if not text:
        return ""
    if contains_sensitive_info(text):
        return "[sensitive transcript content blocked]"
    return text[:MAX_TURN_CHARS]


async def _ensure_voice_session_columns(db: aiosqlite.Connection) -> None:
    cursor = await db.execute("PRAGMA table_info(voice_sessions)")
    existing = {str(row[1]) for row in await cursor.fetchall()}
    columns = {
        "input_chunks_captured": "INTEGER DEFAULT 0",
        "input_chunks_sent": "INTEGER DEFAULT 0",
        "input_bytes_sent": "INTEGER DEFAULT 0",
        "last_input_audio_at": "REAL DEFAULT 0",
        "last_local_mic_rms": "REAL DEFAULT 0",
        "peak_local_mic_rms": "REAL DEFAULT 0",
        "peak_local_mic_rms_since_response": "REAL DEFAULT 0",
        "peak_local_mic_rms_since_response_at": "REAL DEFAULT 0",
        "last_xai_speech_started_at": "REAL DEFAULT 0",
        "last_user_transcript_at": "REAL DEFAULT 0",
        "last_response_done_at": "REAL DEFAULT 0",
    }
    for name, definition in columns.items():
        if name not in existing:
            await db.execute(f"ALTER TABLE voice_sessions ADD COLUMN {name} {definition}")
