from __future__ import annotations

from maya_core.assistant_command_helpers import confirmation_decision
from maya_core.confirmations import approve_task, decline_task, get_pending_confirmation
from maya_core.provenance import provenance_from_source_channel
from maya_core.skill_factory import SkillFactory
from maya_core.storage import complete_task, record_task_event
from maya_voice.confirmation import action_fingerprint, confirm_action, create_pending_confirmation


async def resolve_pending_confirmation(db_path: str, text: str, channel: str) -> str | None:
    decision = confirmation_decision(text)
    if not decision:
        return None
    task = await get_pending_confirmation(db_path, channel)
    if not task:
        return "Nothing is waiting for approval right now."

    task_id = int(task["id"])
    if decision == "approve":
        payload = _task_confirmation_payload(task)
        action_id = f"task:{task_id}"
        await create_pending_confirmation(
            db_path,
            action_id=action_id,
            summary=str(task["title"] or "Pending task approval"),
            payload=payload,
        )
        approval = await confirm_action(
            db_path,
            action_id=action_id,
            approved=True,
            action_fingerprint_value=action_fingerprint(payload),
            approver_provenance=provenance_from_source_channel(channel),
        )
        if approval.get("status") != "approved":
            await record_task_event(db_path, task_id, "confirmation_blocked", str(approval.get("reason_code", "")))
            return f"I cannot approve that yet: {approval.get('reason_code', 'confirmation_failed')}."
        if str(task["action_type"]) == "create_skill_scaffold":
            payload_text = str(task["payload"] or task["details"] or task["title"])
            result = await SkillFactory(db_path).scaffold_skill(payload_text)
            await complete_task(db_path, task_id, result=f"Skill scaffold created at {result['scaffold_path']}.")
            await record_task_event(db_path, task_id, "confirmed", "Approved through W7 owner confirmation and scaffolded.")
            return f"Done. I created the skill scaffold for {result['title']} at {result['scaffold_path']}."
        await approve_task(db_path, task_id)
        await record_task_event(db_path, task_id, "confirmed", "Approved through W7 owner confirmation.")
        return f"Okay, I'll do that now: {task['title']}."

    message = "Okay, I won't do that."
    if decision == "later":
        message = "Okay, I won't do it now. Ask me again when you want it."
    await decline_task(db_path, task_id, message)
    await record_task_event(db_path, task_id, "declined", message)
    return message


def _task_confirmation_payload(task: dict[str, str | int | None]) -> dict[str, str | int | None]:
    return {
        "surface": "task_confirmation",
        "task_id": int(task["id"]),
        "title": task.get("title"),
        "details": task.get("details"),
        "action_type": task.get("action_type"),
        "payload": task.get("payload"),
        "channel": task.get("channel"),
    }
