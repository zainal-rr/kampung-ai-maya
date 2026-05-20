from __future__ import annotations

from harness_idempotency import action_key, begin_action, cached_result, finish_action, mark_unknown, should_pause_unknown
from harness_tools import HarnessToolResult, HarnessTools


async def execute_with_ledger(db_path: str, tools: HarnessTools, state: dict, approved: bool) -> HarnessToolResult:
    workflow = state.get("workflow_type", "general")
    text = state.get("user_text", "")
    action = action_name(workflow, text)
    args = {
        "workflow_type": workflow,
        "text": text,
        "channel": state.get("channel", "imac"),
        "approved": approved,
    }
    key = action_key(
        thread_id=state.get("thread_id", ""),
        run_id=state["run_id"],
        node="execute",
        action=action,
        args=args,
        user_turn_id=state.get("user_turn_id", ""),
    )
    ledger = await begin_action(
        db_path,
        key=key,
        run_id=state["run_id"],
        thread_id=state.get("thread_id", ""),
        node="execute",
        workflow_type=workflow,
        action=action,
        args=args,
    )
    if ledger.get("status") == "succeeded":
        return cached_result(ledger)
    if ledger.get("existing") and ledger.get("status") == "in_progress" and should_pause_unknown(action, text):
        await mark_unknown(db_path, key, "uncertain replay")
        return HarnessToolResult(
            "paused",
            "I found an uncertain previous action. I need to observe before repeating it.",
            requires_approval=True,
            next_step="recovery",
        )
    result = await tools.execute(workflow, text, state.get("channel", "imac"), approved=approved)
    await finish_action(db_path, key, result)
    return result


def action_name(workflow: str, text: str) -> str:
    lowered = text.strip().lower()
    if workflow == "browser" and lowered.startswith(("click ", "choose ", "select ", "press ")):
        return "browser:click"
    if workflow == "browser" and lowered.startswith(("fill ", "enter ", "type ")):
        return "browser:fill"
    return f"{workflow}:execute"
