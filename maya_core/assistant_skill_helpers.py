from __future__ import annotations

from maya_core.storage import create_task, record_task_event, update_task_status


async def queue_skill_scaffold(db_path: str, subject: str, channel: str, prompt: str) -> str:
    task_id = await create_task(
        db_path,
        title=f"Create skill scaffold for {subject}",
        details=subject,
        channel=channel,
        action_type="create_skill_scaffold",
        autonomy_mode="ask_sensitive",
        payload=subject,
    )
    await update_task_status(db_path, task_id, "awaiting_confirmation", result=prompt)
    await record_task_event(db_path, task_id, "awaiting_confirmation", "Awaiting approval for skill scaffold.")
    return prompt
