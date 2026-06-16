from __future__ import annotations

from datetime import datetime, timezone

import aiosqlite


def _task_from_row(row: aiosqlite.Row) -> dict[str, str | int | None]:
    return {
        "id": row["id"],
        "title": row["title"],
        "details": row["details"],
        "status": row["status"],
        "priority": row["priority"],
        "channel": row["channel"],
        "action_type": row["action_type"],
        "autonomy_mode": row["autonomy_mode"],
        "payload": row["payload"],
        "due_at": row["due_at"],
        "last_error": row["last_error"],
        "result": row["result"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


async def get_pending_confirmation(db_path: str, channel: str) -> dict[str, str | int | None] | None:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT *
            FROM tasks
            WHERE status = 'awaiting_confirmation'
              AND channel = ?
              AND datetime(updated_at) >= datetime('now', '-30 minutes')
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 1
            """,
            (channel,),
        )
        row = await cursor.fetchone()
    return _task_from_row(row) if row else None


async def approve_task(db_path: str, task_id: int) -> None:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT due_at FROM tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
        due_at = row[0] if row else None
        if not due_at:
            due_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        await db.execute(
            """
            UPDATE tasks
            SET status = 'pending', autonomy_mode = 'approved', due_at = ?, result = '', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (due_at, task_id),
        )
        await db.commit()


async def decline_task(db_path: str, task_id: int, result: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            UPDATE tasks
            SET status = 'cancelled', result = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (result, task_id),
        )
        await db.commit()
