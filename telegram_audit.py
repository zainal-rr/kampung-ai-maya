from __future__ import annotations

import aiosqlite


async def record_telegram_command(
    db_path: str,
    *,
    chat_id: str,
    command: str,
    args: str,
    mapped_text: str,
    result_type: str,
) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS telegram_command_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT DEFAULT '',
                command TEXT NOT NULL,
                args TEXT DEFAULT '',
                mapped_text TEXT DEFAULT '',
                result_type TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            INSERT INTO telegram_command_audit (
                chat_id, command, args, mapped_text, result_type
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (chat_id, command, args, mapped_text, result_type),
        )
        await db.commit()
