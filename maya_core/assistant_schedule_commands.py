from __future__ import annotations

import re

from maya_core.storage import create_task
from maya_core.time_parser import extract_due_from_text, format_due_text


async def handle_reminder_command(db_path: str, text: str, channel: str) -> str | None:
    match = re.match(r"^(?:remind me to|create task)\s+(.+)$", text, re.IGNORECASE)
    if not match:
        return None
    title, due_at = extract_due_from_text(match.group(1).strip())
    task_id = await create_task(
        db_path,
        title=title,
        details=text,
        channel=channel,
        action_type="follow_up",
        autonomy_mode="auto_safe",
        due_at=due_at,
    )
    return f"Got it. I saved task #{task_id}: {title}, {format_due_text(due_at)}."


async def handle_summary_task_command(db_path: str, text: str, channel: str) -> str | None:
    match = re.match(r"^(?:summarize my day|summarize my history|schedule summary)\s*(.*)$", text, re.IGNORECASE)
    if not match:
        return None
    title, due_at = extract_due_from_text(f"history summary {match.group(1).strip()}".strip())
    task_id = await create_task(
        db_path,
        title=title,
        details=text,
        channel=channel,
        action_type="summarize_history",
        autonomy_mode="auto_safe",
        due_at=due_at,
    )
    return f"Done. I scheduled summary task #{task_id}, {format_due_text(due_at)}."
