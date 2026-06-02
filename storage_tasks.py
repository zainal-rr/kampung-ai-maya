from __future__ import annotations

import aiosqlite

from retention_policy import touch_task_activity


TASK_COLUMNS = (
    "id, title, details, status, priority, channel, action_type, "
    "autonomy_mode, payload, due_at, last_error, result, created_at, updated_at"
)


def task_dict(row: aiosqlite.Row) -> dict[str, str | int | None]:
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


async def create_task(
    db_path: str,
    title: str,
    details: str = "",
    channel: str = "imac",
    action_type: str = "follow_up",
    autonomy_mode: str = "suggest",
    due_at: str | None = None,
    payload: str = "",
    priority: int = 2,
) -> int:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            INSERT INTO tasks (
                title, details, channel, action_type, autonomy_mode,
                due_at, payload, priority
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (title, details, channel, action_type, autonomy_mode, due_at, payload, priority),
        )
        await db.commit()
        task_id = int(cursor.lastrowid)
    await touch_task_activity(db_path, task_id, "created task", "task")
    return task_id


async def list_tasks(
    db_path: str,
    statuses: tuple[str, ...] = ("pending", "running", "awaiting_confirmation"),
    limit: int = 10,
) -> list[dict[str, str | int | None]]:
    placeholders = ", ".join("?" for _ in statuses)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""
            SELECT {TASK_COLUMNS}
            FROM tasks
            WHERE status IN ({placeholders})
            ORDER BY
                CASE WHEN due_at IS NULL THEN 1 ELSE 0 END,
                due_at ASC,
                priority DESC,
                created_at ASC
            LIMIT ?
            """,
            (*statuses, limit),
        )
        rows = await cursor.fetchall()
    return [task_dict(row) for row in rows]


async def claim_due_tasks(
    db_path: str,
    now_iso: str,
    limit: int = 5,
) -> list[dict[str, str | int | None]]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""
            SELECT {TASK_COLUMNS}
            FROM tasks
            WHERE status = 'pending'
              AND due_at IS NOT NULL
              AND due_at <= ?
            ORDER BY due_at ASC, priority DESC, created_at ASC
            LIMIT ?
            """,
            (now_iso, limit),
        )
        rows = await cursor.fetchall()
        task_ids = [row["id"] for row in rows]
        for task_id in task_ids:
            await db.execute(
                """
                UPDATE tasks
                SET status = 'running', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (task_id,),
            )
        await db.commit()
    for task_id in task_ids:
        await touch_task_activity(db_path, int(task_id), "claimed due task", "task")
    return [task_dict(row) for row in rows]


async def update_task_status(
    db_path: str,
    task_id: int,
    status: str,
    result: str = "",
    last_error: str = "",
) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            UPDATE tasks
            SET status = ?, result = ?, last_error = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, result, last_error, task_id),
        )
        await db.commit()
    await touch_task_activity(db_path, task_id, status, "task")


async def complete_task(db_path: str, task_id: int, result: str = "") -> None:
    await update_task_status(db_path, task_id, "completed", result=result)


async def fail_task(db_path: str, task_id: int, error: str) -> None:
    await update_task_status(db_path, task_id, "failed", last_error=error)


async def cancel_matching_tasks(db_path: str, query: str = "", task_id: int | None = None) -> list[dict[str, str | int | None]]:
    tasks = await list_tasks(db_path, limit=50)
    matches = [task for task in tasks if _matches_task(task, query, task_id)]
    for task in matches:
        await update_task_status(
            db_path,
            int(task["id"]),
            "cancelled",
            result="Cancelled by user request.",
        )
        await record_task_event(db_path, int(task["id"]), "cancelled", "Cancelled by user request.")
    return matches


async def record_task_event(db_path: str, task_id: int, event: str, details: str = "") -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO task_events (task_id, event, details) VALUES (?, ?, ?)",
            (task_id, event, details),
        )
        await db.commit()
    await touch_task_activity(db_path, task_id, event, "task_event")


def _matches_task(task: dict[str, str | int | None], query: str, task_id: int | None) -> bool:
    if task_id is not None:
        return int(task["id"]) == task_id
    cleaned = query.strip().lower()
    if not cleaned or cleaned in {"all", "everything", "all tasks"}:
        return True
    haystack = f"{task['title']} {task['details']}".lower()
    tokens = [token for token in cleaned.split() if len(token) > 2 and token not in {"the", "my", "task", "tasks"}]
    return bool(tokens) and all(token in haystack for token in tokens)
