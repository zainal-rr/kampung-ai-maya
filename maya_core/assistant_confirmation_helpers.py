from __future__ import annotations

from maya_core.assistant_command_helpers import confirmation_decision
from confirmations import approve_task, decline_task, get_pending_confirmation
from skill_factory import SkillFactory
from storage import complete_task, record_task_event


async def resolve_pending_confirmation(db_path: str, text: str, channel: str) -> str | None:
    decision = confirmation_decision(text)
    if not decision:
        return None
    task = await get_pending_confirmation(db_path, channel)
    if not task:
        return "Nothing is waiting for approval right now."

    task_id = int(task["id"])
    if decision == "approve":
        if str(task["action_type"]) == "create_skill_scaffold":
            payload = str(task["payload"] or task["details"] or task["title"])
            result = await SkillFactory(db_path).scaffold_skill(payload)
            await complete_task(db_path, task_id, result=f"Skill scaffold created at {result['scaffold_path']}.")
            await record_task_event(db_path, task_id, "confirmed", "Approved and scaffolded in chat.")
            return f"Done. I created the skill scaffold for {result['title']} at {result['scaffold_path']}."
        await approve_task(db_path, task_id)
        await record_task_event(db_path, task_id, "confirmed", "Approved by user in chat.")
        return f"Okay, I'll do that now: {task['title']}."

    message = "Okay, I won't do that."
    if decision == "later":
        message = "Okay, I won't do it now. Ask me again when you want it."
    await decline_task(db_path, task_id, message)
    await record_task_event(db_path, task_id, "declined", message)
    return message
