from __future__ import annotations

import aiosqlite


async def init_telegram_delivery_state_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS telegram_delivery_state (
                chat_id TEXT PRIMARY KEY,
                last_voice_message_id INTEGER,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


async def last_voice_message_id(db_path: str, chat_id: int) -> int | None:
    await init_telegram_delivery_state_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT last_voice_message_id FROM telegram_delivery_state WHERE chat_id = ?",
            (str(chat_id),),
        )
        row = await cursor.fetchone()
    return int(row[0]) if row and row[0] is not None else None


async def save_last_voice_message_id(db_path: str, chat_id: int, message_id: int) -> None:
    await init_telegram_delivery_state_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO telegram_delivery_state (chat_id, last_voice_message_id, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(chat_id) DO UPDATE SET
                last_voice_message_id = excluded.last_voice_message_id,
                updated_at = CURRENT_TIMESTAMP
            """,
            (str(chat_id), message_id),
        )
        await db.commit()
