from __future__ import annotations

import re

import aiosqlite

from maya_core.storage import create_task, record_task_event, update_task_status
from maya_core.storage_tasks import TASK_COLUMNS, task_dict
from maya_core.time_parser import extract_due_from_text, format_due_text


async def handle_waiting_on(db_path: str, text: str, channel: str) -> str | None:
    create_subject = _create_subject(text)
    if create_subject:
        return await create_waiting_on(db_path, create_subject, channel, text)
    list_request = _is_list_request(text)
    if list_request:
        return format_waiting_on(await list_waiting_on(db_path))
    clear_subject = _clear_subject(text)
    if clear_subject:
        return await clear_waiting_on(db_path, clear_subject)
    return None


async def create_waiting_on(db_path: str, subject: str, channel: str, details: str = "") -> str:
    title, due_at = extract_due_from_text(subject)
    task_id = await create_task(
        db_path,
        title=title,
        details=details or subject,
        channel=channel,
        action_type="waiting_on",
        autonomy_mode="observe",
        due_at=due_at,
    )
    await record_task_event(db_path, task_id, "waiting_on", "Waiting-on item created.")
    return f"Got it. I am tracking waiting-on #{task_id}: {title}, {format_due_text(due_at)}."


async def list_waiting_on(db_path: str, limit: int = 10) -> list[dict[str, str | int | None]]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""
            SELECT {TASK_COLUMNS}
            FROM tasks
            WHERE action_type = 'waiting_on' AND status IN ('pending', 'running')
            ORDER BY due_at IS NULL, due_at ASC, created_at ASC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
    return [task_dict(row) for row in rows]


def format_waiting_on(items: list[dict[str, str | int | None]]) -> str:
    if not items:
        return "You are not waiting on anything I am tracking right now."
    lines = []
    for item in items:
        due = f" {format_due_text(str(item['due_at']))}" if item["due_at"] else ""
        lines.append(f"{len(lines) + 1}) #{item['id']} {item['title']}{due}")
    return "Waiting on:\n" + "\n".join(lines)


async def clear_waiting_on(db_path: str, subject: str) -> str:
    items = await list_waiting_on(db_path, limit=50)
    matches = [item for item in items if _matches(item, subject)]
    if not matches:
        return "I could not find a waiting-on item matching that."
    for item in matches:
        await update_task_status(db_path, int(item["id"]), "completed", "No longer waiting.")
        await record_task_event(db_path, int(item["id"]), "cleared", "Waiting-on item cleared.")
    if len(matches) == 1:
        return f"Done. I cleared waiting-on #{matches[0]['id']}."
    return f"Done. I cleared {len(matches)} waiting-on items."


def _create_subject(text: str) -> str | None:
    match = re.match(r"^(?:i am waiting on|i'm waiting on|track that i am waiting for|track waiting on)\s+(.+)$", text, re.I)
    return match.group(1).strip(" .") if match else None


def _clear_subject(text: str) -> str | None:
    match = re.match(r"^(?:clear|remove|done with)\s+waiting(?:-|\s)?on\s+(.+)$", text, re.I)
    return match.group(1).strip(" .") if match else None


def _is_list_request(text: str) -> bool:
    return " ".join(text.lower().split()) in {"what am i waiting on", "show waiting on", "list waiting on"}


def _matches(item: dict[str, str | int | None], subject: str) -> bool:
    haystack = f"{item['title']} {item['details']}".lower()
    tokens = [token for token in subject.lower().split() if len(token) > 2]
    return bool(tokens) and all(token in haystack for token in tokens)
