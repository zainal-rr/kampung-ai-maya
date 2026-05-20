from __future__ import annotations

import re

from assistant_command_helpers import confirmation_decision
from harness_graph import HarnessGraphRunner
from harness_artifact_store import latest_artifacts
from harness_resume import build_resume_summary
from harness_state import initial_harness_state
from harness_store import (
    finish_run,
    get_active_run,
    latest_events,
    list_active_runs,
    new_run_id,
    record_event,
    resolve_approval,
)
from harness_workflows import classify_workflow
from storage import delete_preference, get_preference, upsert_preference


START_MARKERS = (
    "check flight",
    "find flight",
    "search flight",
    "book flight",
    "browse ",
    "search online",
    "google",
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
    "draw ",
    "create drawing",
    "open project",
    "switch project",
    "self heal",
    "repair maya",
    "book me a hotel",
    "look at my screen",
    "open ",
    "switch to ",
    "press ",
    "type ",
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
    "compare them",
    "click ",
    "fill ",
)
STOP_MARKERS = {"stop workflow", "close workflow", "end workflow", "cancel workflow"}
RESUME_MARKERS = {"what are you working on", "where did we stop", "what is pending", "workflow status"}
ARTIFACT_MARKERS = {"what files did you create", "show me the latest artifact", "which screenshot did you use"}


class HarnessRouter:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.runner = HarnessGraphRunner(db_path)

    async def handle(self, text: str, channel: str) -> str | None:
        cleaned = " ".join(text.strip().split())
        if not cleaned:
            return None
        decision = confirmation_decision(cleaned)
        if decision:
            return await self._confirmation(decision, channel)
        lowered = cleaned.lower()
        selection = await self._selection(cleaned, channel)
        if selection is not None:
            return selection
        if lowered in STOP_MARKERS:
            return await self._stop(channel)
        if lowered in RESUME_MARKERS:
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
        thread_id = _thread_id(workflow_type, text, run_id)
        state = initial_harness_state(
            run_id=run_id,
            thread_id=thread_id,
            channel=channel,
            user_text=text,
            workflow_type=workflow_type,
        )
        result = await self.runner.run(state)
        return str(result.get("final_response") or "I started the workflow.")

    async def _continue(self, active: dict, text: str, channel: str) -> str:
        result = await self.runner.resume(active, text)
        return str(result.get("final_response") or "I continued the workflow.")

    async def _confirmation(self, decision: str, channel: str) -> str | None:
        active = await get_active_run(self.db_path, channel)
        if not active:
            return None
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
        return str(result.get("final_response") or "Done. I continued after your approval.")

    async def _stop(self, channel: str) -> str:
        active = await get_active_run(self.db_path, channel)
        if not active:
            return "No active workflow right now."
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
        from harness_store import get_run

        run = await get_run(self.db_path, run_ids[index])
        if not run:
            return "That workflow is not available anymore."
        return await self._continue(run, "continue", channel)


def _is_start(lowered: str) -> bool:
    return any(marker in lowered for marker in START_MARKERS)


def _is_followup(lowered: str) -> bool:
    return any(marker in lowered for marker in FOLLOWUP_MARKERS)


def _thread_id(workflow_type: str, text: str, run_id: str) -> str:
    if run_id.startswith("task_"):
        return f"harness:background:{run_id.removeprefix('task_')}"
    return f"harness:{run_id}"
