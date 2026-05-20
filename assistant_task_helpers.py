from __future__ import annotations

import re

from time_parser import format_due_text
from storage import create_task, record_task_event, update_task_status


def parse_task_delete_request(text: str) -> tuple[int | None, str] | None:
    match = re.match(
        r"^(?:delete|remove|cancel)\s+(?:my\s+)?(?:task|tasks)(?:\s+#?(\d+)|\s+(?:to|about|for)\s+(.+)|\s+(.+))?$",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    task_id = int(match.group(1)) if match.group(1) else None
    query = (match.group(2) or match.group(3) or "").strip()
    return task_id, query


def format_open_tasks(tasks: list[dict[str, str | int | None]]) -> str:
    if not tasks:
        return "You don't have any open tasks right now."
    lines = []
    for task in tasks:
        due_text = f" {format_due_text(str(task['due_at']))}" if task["due_at"] else ""
        lines.append(f"#{task['id']} {task['title']} ({task['status']}){due_text}")
    return "Open tasks:\n" + "\n".join(lines)


async def create_sensitive_send_task(
    db_path: str,
    subject: str,
    channel: str,
    action_type: str,
) -> str:
    payload = f"telegram|literal:{subject}"
    title = f"Send this to Telegram: {subject}"
    lowered = subject.lower()
    if "task" in lowered:
        payload = "telegram|task_list"
        title = "Send current task list to Telegram"
    elif "summary" in lowered or "history" in lowered:
        payload = "telegram|history_summary"
        title = "Send recent summary to Telegram"

    task_id = await create_task(
        db_path,
        title=title,
        details=subject,
        channel=channel,
        action_type=action_type,
        autonomy_mode="ask_sensitive",
        payload=payload,
    )
    await update_task_status(
        db_path,
        task_id,
        "awaiting_confirmation",
        result="I can do that. Do you want me to do it?",
    )
    await record_task_event(db_path, task_id, "awaiting_confirmation", "Awaiting natural-language approval.")
    return "I can do that. Do you want me to do it?"
