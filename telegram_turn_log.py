from __future__ import annotations

import aiosqlite


async def init_telegram_turn_log_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS telegram_turn_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                input_type TEXT DEFAULT '',
                prompt_preview TEXT DEFAULT '',
                status TEXT NOT NULL,
                duration_ms INTEGER DEFAULT 0,
                response_chars INTEGER DEFAULT 0,
                response_preview TEXT DEFAULT '',
                error TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor = await db.execute("PRAGMA table_info(telegram_turn_events)")
        columns = {str(row[1]) for row in await cursor.fetchall()}
        if "response_preview" not in columns:
            await db.execute("ALTER TABLE telegram_turn_events ADD COLUMN response_preview TEXT DEFAULT ''")
        await db.commit()


async def record_telegram_turn_received(
    db_path: str,
    *,
    chat_id: int | str,
    input_type: str,
    prompt: str,
) -> int:
    """Durable intake guard: insert a 'received' turn row BEFORE any
    processing. Returns the row id so the handler can finalize it later.
    A crash or task cancellation mid-handling leaves a visible orphaned
    'received' row instead of a silently vanished message."""
    await init_telegram_turn_log_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            INSERT INTO telegram_turn_events (chat_id, input_type, prompt_preview, status)
            VALUES (?, ?, ?, 'received')
            """,
            (str(chat_id), input_type, prompt[:300]),
        )
        await db.commit()
        return int(cursor.lastrowid or 0)


async def finalize_telegram_turn(
    db_path: str,
    turn_id: int,
    *,
    status: str,
    duration_ms: int = 0,
    response_chars: int = 0,
    response_preview: str = "",
    error: str = "",
) -> None:
    await init_telegram_turn_log_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            UPDATE telegram_turn_events
            SET status = ?, duration_ms = ?, response_chars = ?, response_preview = ?, error = ?
            WHERE id = ?
            """,
            (status, int(duration_ms), int(response_chars), response_preview[:1000], error[:500], int(turn_id)),
        )
        await db.commit()


async def count_orphaned_received_turns(db_path: str) -> int:
    """Turns that were received but never finalized: the disappearance signal."""
    await init_telegram_turn_log_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM telegram_turn_events WHERE status = 'received'")
        row = await cursor.fetchone()
    return int(row[0]) if row else 0


async def record_telegram_turn(
    db_path: str,
    *,
    chat_id: int | str,
    input_type: str,
    prompt: str,
    status: str,
    duration_ms: int = 0,
    response_chars: int = 0,
    response_preview: str = "",
    error: str = "",
) -> None:
    await init_telegram_turn_log_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO telegram_turn_events (
                chat_id, input_type, prompt_preview, status, duration_ms, response_chars, response_preview, error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(chat_id),
                input_type,
                prompt[:300],
                status,
                int(duration_ms),
                int(response_chars),
                response_preview[:1000],
                error[:500],
            ),
        )
        await db.commit()


async def latest_telegram_turn_text(db_path: str) -> str:
    await init_telegram_turn_log_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT input_type, prompt_preview, status, duration_ms, response_chars, response_preview, error, created_at
            FROM telegram_turn_events
            ORDER BY id DESC
            LIMIT 1
            """
        )
        row = await cursor.fetchone()
    if not row:
        return "No Telegram turn event recorded yet."
    lines = [
        "Last Telegram turn:",
        f"1) status: {row['status']}",
        f"2) input: {row['input_type']}",
        f"3) duration ms: {row['duration_ms']}",
        f"4) response chars: {row['response_chars']}",
        f"5) prompt: {row['prompt_preview']}",
        f"6) time: {row['created_at']}",
    ]
    if row["response_preview"]:
        lines.append(f"7) response: {row['response_preview']}")
    if row["error"]:
        lines.append(f"8) error: {row['error']}")
    return "\n".join(lines)
