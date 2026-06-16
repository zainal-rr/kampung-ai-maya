from __future__ import annotations

import os
import re

from maya_core.assistant_command_helpers import confirmation_decision
from maya_harness.harness_command_bypass import is_fresh_artifact_request
from maya_harness.harness_graph import HarnessGraphRunner
from maya_harness.harness_artifact_store import latest_artifacts
from maya_harness.harness_resume import build_resume_summary
from maya_harness.harness_state import initial_harness_state
from maya_harness.harness_store import (
    finish_run,
    get_active_run,
    latest_events,
    list_active_runs,
    new_run_id,
    record_event,
    resolve_approval,
)
from maya_harness.harness_workflows import classify_workflow
from storage import delete_preference, get_preference, upsert_preference


# Bare command verbs only count when the message *starts* with them, so chat like
# "what type of pasta", "is the mall open today", or "press release" stays in the
# normal conversation lanes instead of hijacking a harness workflow.
START_COMMAND_RE = re.compile(
    r"^(?:please\s+|maya[,\s]+)?"
    r"(?:open|switch\s+to|press|type|draw|browse|google)\b",
    re.IGNORECASE,
)
START_MARKERS = (
    "check flight",
    "find flight",
    "find flights",
    "search flight",
    "search flights",
    "book flight",
    "search online",
    "make presentation",
    "create presentation",
    "write a word",
    "create a docx",
    "make an excel",
    "create an excel",
    "write an excel",
    "make a spreadsheet",
    "create a spreadsheet",
    "make an xlsx",
    "create an xlsx",
    "create an md",
    "make a markdown",
    "create drawing",
    "open project",
    "switch project",
    "self heal",
    "repair maya",
    "book me a hotel",
    "look at my screen",
)
FOLLOWUP_MARKERS = (
    "continue",
    "what about now",
    "how about now",
    "change the date",
    "find cheaper",
    "make it cheaper",
    "open it",
    "show me",
    "save it",
    "use this project",
    "click ",
    "fill ",
)
STOP_MARKERS = {"stop workflow", "close workflow", "end workflow", "cancel workflow"}
RESUME_MARKERS = {"what are you working on", "where did we stop", "what is pending", "workflow status"}
ARTIFACT_MARKERS = {"what files did you create", "show me the latest artifact", "which screenshot did you use"}
COMMAND_BYPASS_MARKERS = {
    "open the last document",
    "open latest document",
    "what was the last document you created",
    "what is the last document you created",
    "what was the latest document you created",
    "what is the latest document you created",
    "what document did you just create",
    "what document did you create just now",
    "what file did you just create",
    "what file did you create just now",
    "what did you just create",
    "what did you create just now",
    "what document did you create",
    "what file did you create",
    "what was the last document",
    "what is the last document",
    "last document",
    "latest document",
}
FILE_OPEN_BYPASS_RE = re.compile(
    r"^(?:open|show(?: me)?)\s+(?:latest\s+|the\s+latest\s+)?"
    r"(?:word|docx|document|powerpoint|presentation|pptx|excel|spreadsheet|xlsx|markdown|md)\b",
    re.I,
)


class HarnessRouter:
    def __init__(self, db_path: str, planner_llm=None):
        self.db_path = db_path
        self.runner = HarnessGraphRunner(db_path, planner_llm=planner_llm)
        self.last_lane = "LangGraph harness"
        self.last_reason = "persistent workflow"
        self.last_cost_recorded = False

    async def handle(self, text: str, channel: str) -> str | None:
        cleaned = " ".join(text.strip().split())
        if not cleaned:
            return None
        lowered = cleaned.lower()
        if lowered in STOP_MARKERS:
            # "stop workflow" must beat confirmation_decision, which would
            # otherwise read it as a bare decline and drop it unhandled.
            return await self._stop(channel)
        decision = confirmation_decision(cleaned)
        if decision:
            return await self._confirmation(decision, channel)
        lowered_key = lowered.rstrip("?.! ")
        if lowered_key in COMMAND_BYPASS_MARKERS or FILE_OPEN_BYPASS_RE.match(cleaned):
            return None
        if is_fresh_artifact_request(cleaned):
            return None
        selection = await self._selection(cleaned, channel)
        if selection is not None:
            return selection
        if lowered in RESUME_MARKERS or lowered == "continue":
            await self._save_resume_choices(channel)
            return await build_resume_summary(self.db_path, channel)
        if lowered in ARTIFACT_MARKERS:
            return await self._artifact_summary(channel)
        if lowered == "open the last file":
            return await self._last_file(channel)
        active = await get_active_run(self.db_path, channel)
        if _is_followup(lowered):
            runs = await list_active_runs(self.db_path, channel)
            if len(runs) > 1:
                await upsert_preference(
                    self.db_path,
                    f"maya_harness_choices:{channel}",
                    ",".join(str(run["run_id"]) for run in runs),
                    source="harness",
                )
                return await build_resume_summary(self.db_path, channel)
            if runs:
                return await self._continue(runs[0], cleaned, channel)
        if _is_start(lowered):
            return await self._start(cleaned, channel)
        return None

    async def _start(self, text: str, channel: str) -> str:
        workflow_type = classify_workflow(text)
        run_id = new_run_id()
        thread_id = _thread_id(run_id)
        state = initial_harness_state(
            run_id=run_id,
            thread_id=thread_id,
            channel=channel,
            user_text=text,
            workflow_type=workflow_type,
        )
        if self.runner.planner_llm is not None and os.getenv("MAYA_AGENTIC_LOOP", "0") == "1":
            state["agentic_loop"] = True
        result = await self.runner.run(state)
        self._remember_route(result)
        return str(result.get("final_response") or "I started the workflow.")

    async def _continue(self, active: dict, text: str, channel: str) -> str:
        result = await self.runner.resume(active, text)
        self._remember_route(result)
        response = str(result.get("final_response") or "I continued the workflow.")
        return _continuing_prefix(active) + "\n" + response

    async def _confirmation(self, decision: str, channel: str) -> str | None:
        active = await get_active_run(self.db_path, channel)
        if not active:
            return None
        if str(active.get("workflow_type") or "").startswith("artisan"):
            return await self._artisan_confirmation(active, decision)
        state = await self.runner.get_snapshot(active)
        if not state.get("pending_approval") and active.get("status") != "paused":
            return None
        if decision != "approve":
            await resolve_approval(self.db_path, active["run_id"], "declined")
            await finish_run(self.db_path, active["run_id"], status="cancelled")
            await self.runner.update_checkpoint(active, {"graph_status": "cancelled", "pending_approval": {}, "approval_result": "declined"})
            return "Okay, I won't do that."
        await resolve_approval(self.db_path, active["run_id"], "approved")
        result = await self.runner.resume(active, "approved", approval_result="approved")
        self._remember_route(result)
        return str(result.get("final_response") or "Done. I continued after your approval.")

    async def _artisan_confirmation(self, active: dict, decision: str) -> str | None:
        state = dict(active.get("state") or {})
        if state.get("approval_state") != "repo_approval_required" and active.get("status") != "paused":
            return None
        if decision != "approve":
            await resolve_approval(self.db_path, active["run_id"], "declined")
            await finish_run(self.db_path, active["run_id"], status="cancelled")
            return "Okay, I won't apply the Artisan repo changes."
        await resolve_approval(self.db_path, active["run_id"], "approved")
        await finish_run(self.db_path, active["run_id"], status="approved_waiting_manual_apply")
        worktree = state.get("working_directory", "")
        original = state.get("original_repo_path", "")
        return (
            "Approved. I recorded approval for the Artisan repo changes, but I did not apply them automatically.\n"
            f"1) isolated worktree: {worktree}\n"
            f"2) original repo: {original}\n"
            "3) next: review the worktree diff, then apply intentionally."
        )

    async def _stop(self, channel: str) -> str:
        active = await get_active_run(self.db_path, channel)
        browser_task = await get_preference(self.db_path, "maya_browser_workflow")
        await delete_preference(self.db_path, "maya_browser_workflow")
        if not active:
            return "Okay. I closed the active browser task." if browser_task else "No active workflow right now."
        await record_event(self.db_path, active["run_id"], "cancelled", "Cancelled by user.")
        await finish_run(self.db_path, active["run_id"], status="cancelled")
        await self.runner.update_checkpoint(active, {"graph_status": "cancelled", "pending_approval": {}})
        return "Okay. I closed the active workflow."

    async def status(self, channel: str) -> str:
        active = await get_active_run(self.db_path, channel)
        if not active:
            return "No active workflow right now."
        snapshot = await self.runner.get_snapshot(active)
        events = await latest_events(self.db_path, active["run_id"])
        lines = [f"{item['event']}: {item['details']}" for item in events[-5:]]
        return f"Active workflow: {active['goal']}\nStatus: {snapshot.get('graph_status', active['status'])}\n" + "\n".join(lines)

    async def _artifact_summary(self, channel: str) -> str:
        active = await get_active_run(self.db_path, channel)
        artifacts = await latest_artifacts(self.db_path, active["run_id"] if active else None, limit=5)
        if not artifacts:
            return "No workflow artifacts logged yet."
        lines = [f"{idx}) {item['kind']}: {item['path'] or item['url'] or item['summary']}" for idx, item in enumerate(artifacts, start=1)]
        return "Latest artifacts:\n" + "\n".join(lines)

    async def _last_file(self, channel: str) -> str:
        active = await get_active_run(self.db_path, channel)
        artifacts = await latest_artifacts(self.db_path, active["run_id"] if active else None, limit=8)
        for item in artifacts:
            if item.get("path"):
                return f"Last file: {item['path']}"
        return "No file artifact is available yet."

    async def _save_resume_choices(self, channel: str) -> None:
        runs = await list_active_runs(self.db_path, channel)
        if len(runs) <= 1:
            return
        await upsert_preference(
            self.db_path,
            f"maya_harness_choices:{channel}",
            ",".join(str(run["run_id"]) for run in runs),
            source="harness",
        )

    async def _selection(self, text: str, channel: str) -> str | None:
        raw = await get_preference(self.db_path, f"maya_harness_choices:{channel}")
        if not raw:
            return None
        match = re.match(r"^(?:continue\s+)?(\d+)$", text.strip(), re.IGNORECASE)
        if not match:
            return None
        run_ids = [item for item in raw.split(",") if item]
        index = int(match.group(1)) - 1
        await delete_preference(self.db_path, f"maya_harness_choices:{channel}")
        if index < 0 or index >= len(run_ids):
            return "That workflow choice is not available anymore."
        from maya_harness.harness_store import get_run

        run = await get_run(self.db_path, run_ids[index])
        if not run:
            return "That workflow is not available anymore."
        return await self._continue(run, "continue", channel)

    def _remember_route(self, result: dict) -> None:
        self.last_lane = str(result.get("model_lane") or "LangGraph harness")
        self.last_reason = "persistent workflow"
        self.last_cost_recorded = bool(result.get("cost_recorded"))


def _is_start(lowered: str) -> bool:
    return bool(START_COMMAND_RE.match(lowered)) or any(
        marker in lowered for marker in START_MARKERS
    )


def _is_followup(lowered: str) -> bool:
    if lowered.startswith(("compare ", "explain ", "what is ", "what are ")):
        return False
    return any(marker in lowered for marker in FOLLOWUP_MARKERS)


def _thread_id(run_id: str) -> str:
    return f"harness:{run_id}"


def _continuing_prefix(active: dict) -> str:
    workflow = str(active.get("workflow_type") or "workflow")
    goal = str(active.get("goal") or "").strip()
    return f"Continuing: {workflow}" + (f" for {goal}." if goal else ".")
