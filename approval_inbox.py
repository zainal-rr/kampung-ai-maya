from __future__ import annotations

import aiosqlite

from harness_store import init_harness_db
from skill_store import init_skill_db
from storage import list_tasks


async def approval_inbox_text(db_path: str) -> str:
    items = await approval_items(db_path)
    if not items:
        return "Nothing is waiting for approval right now."
    lines = ["Waiting for approval:"]
    for index, item in enumerate(items[:8], start=1):
        lines.append(f"{index}) {item}")
    return "\n".join(lines)


async def approval_items(db_path: str) -> list[str]:
    task_items = await _task_approvals(db_path)
    harness_items = await _harness_approvals(db_path)
    skill_items = await _skill_proposals(db_path)
    return task_items + harness_items + skill_items


async def _task_approvals(db_path: str) -> list[str]:
    tasks = await list_tasks(db_path, statuses=("awaiting_confirmation",), limit=10)
    return [f"task #{task['id']}: {task['title']}" for task in tasks]


async def _harness_approvals(db_path: str) -> list[str]:
    await init_harness_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT run_id, action, details
            FROM harness_approvals
            WHERE status = 'pending'
            ORDER BY id DESC
            LIMIT 10
            """
        )
        rows = await cursor.fetchall()
    return [f"workflow {row['run_id']}: {row['action']} {row['details']}".strip() for row in rows]


async def _skill_proposals(db_path: str) -> list[str]:
    await init_skill_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT skill_id, summary, status
            FROM skill_proposals
            WHERE status IN ('draft', 'proposed')
            ORDER BY id DESC
            LIMIT 10
            """
        )
        rows = await cursor.fetchall()
    return [f"skill proposal {row['skill_id']}: {row['summary']}" for row in rows]
