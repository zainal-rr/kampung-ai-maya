from __future__ import annotations

import json
from pathlib import Path

import aiosqlite


async def init_telegram_delivery_log_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS telegram_delivery_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                input_type TEXT DEFAULT '',
                status TEXT NOT NULL,
                text_chars INTEGER DEFAULT 0,
                files_json TEXT DEFAULT '[]',
                error TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


async def record_telegram_delivery(
    db_path: str,
    *,
    chat_id: int | str,
    input_type: str,
    status: str,
    text_chars: int,
    files: list[dict[str, str]] | list[Path],
    error: str = "",
) -> None:
    await init_telegram_delivery_log_db(db_path)
    normalized = [
        {"path": str(item), "status": "planned"} if isinstance(item, Path) else dict(item)
        for item in files
    ]
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO telegram_delivery_events (chat_id, input_type, status, text_chars, files_json, error)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (str(chat_id), input_type, status, int(text_chars), json.dumps(normalized), error[:500]),
        )
        await db.commit()


async def latest_telegram_delivery_text(db_path: str) -> str:
    await init_telegram_delivery_log_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT chat_id, input_type, status, text_chars, files_json, error, created_at
            FROM telegram_delivery_events
            ORDER BY id DESC
            LIMIT 1
            """
        )
        row = await cursor.fetchone()
    if not row:
        return "No Telegram delivery event recorded yet."
    files = json.loads(row["files_json"] or "[]")
    file_lines = [f"{idx}) {item.get('status', '')}: {item.get('path', '')}" for idx, item in enumerate(files, 1)]
    lines = [
        "Last Telegram delivery:",
        f"1) status: {row['status']}",
        f"2) input: {row['input_type']}",
        f"3) text chars: {row['text_chars']}",
        f"4) time: {row['created_at']}",
    ]
    if file_lines:
        lines.append("5) files:")
        lines.extend(file_lines)
    if row["error"]:
        lines.append(f"6) error: {row['error']}")
    return "\n".join(lines)
