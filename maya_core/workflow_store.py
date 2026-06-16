from __future__ import annotations

import json

import aiosqlite

from retention_policy import touch_task_activity
from storage_tasks import task_dict


TASK_SELECT = (
    "tasks.id, title, details, tasks.status, priority, channel, action_type, "
    "autonomy_mode, payload, due_at, tasks.last_error AS last_error, "
    "tasks.result AS result, tasks.created_at, tasks.updated_at"
)


async def init_workflow_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL UNIQUE,
                plan_json TEXT DEFAULT '[]',
                context_json TEXT DEFAULT '{}',
                status TEXT DEFAULT 'running',
                current_step INTEGER DEFAULT 0,
                last_error TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


async def begin_workflow(db_path: str, task_id: int, plan: list[str]) -> dict[str, object]:
    await init_workflow_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO workflow_runs (task_id, plan_json, status, current_step)
            VALUES (?, ?, 'running', 0)
            ON CONFLICT(task_id) DO NOTHING
            """,
            (task_id, json.dumps(plan)),
        )
        await db.commit()
    await touch_task_activity(db_path, task_id, "workflow started", "workflow")
    return await get_workflow(db_path, task_id) or {}


async def get_workflow(db_path: str, task_id: int) -> dict[str, object] | None:
    await init_workflow_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM workflow_runs WHERE task_id = ?", (task_id,))
        row = await cursor.fetchone()
    if not row:
        return None
    data = dict(row)
    data["context"] = json.loads(str(data.pop("context_json") or "{}"))
    data["plan"] = json.loads(str(data.pop("plan_json") or "[]"))
    return data


async def save_workflow_progress(
    db_path: str,
    task_id: int,
    *,
    current_step: int,
    context: dict[str, object],
) -> None:
    await init_workflow_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            UPDATE workflow_runs
            SET current_step = ?, context_json = ?, status = 'running', updated_at = CURRENT_TIMESTAMP
            WHERE task_id = ?
            """,
            (current_step, json.dumps(context), task_id),
        )
        await db.commit()
    await touch_task_activity(db_path, task_id, "workflow progress", "workflow")


async def finish_workflow(
    db_path: str,
    task_id: int,
    *,
    status: str,
    context: dict[str, object],
    error: str = "",
) -> None:
    await init_workflow_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            UPDATE workflow_runs
            SET status = ?, context_json = ?, last_error = ?, updated_at = CURRENT_TIMESTAMP
            WHERE task_id = ?
            """,
            (status, json.dumps(context), error, task_id),
        )
        await db.commit()
    await touch_task_activity(db_path, task_id, status, "workflow")


async def resumable_running_tasks(db_path: str, limit: int = 5) -> list[dict[str, str | int | None]]:
    await init_workflow_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""
            SELECT {TASK_SELECT}
            FROM tasks
            JOIN workflow_runs ON workflow_runs.task_id = tasks.id
            WHERE tasks.status = 'running'
              AND workflow_runs.status = 'running'
            ORDER BY workflow_runs.updated_at ASC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
    return [task_dict(row) for row in rows]
