from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone

from maya_core.agent_actions import AgentActionExecutor
from maya_core.agent_planner import AgentPlanner
from maya_core.autonomy import AutonomyPolicy
from maya_harness.harness_graph import HarnessGraphRunner
from maya_core.routine_store import claim_due_routines
from maya_core.storage import (
    create_task,
    claim_due_tasks,
    complete_task,
    fail_task,
    record_task_event,
    update_task_status,
)
from maya_core.workflow_store import (
    begin_workflow,
    finish_workflow,
    get_workflow,
    resumable_running_tasks,
    save_workflow_progress,
)


class AgentRuntime:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.executor = AgentActionExecutor(db_path)
        self.harness = HarnessGraphRunner(db_path)
        self.planner = AgentPlanner()
        self.policy = AutonomyPolicy()
        self.poll_seconds = int(os.getenv("AGENT_POLL_SECONDS", "20"))
        self.running = False

    async def run(self) -> None:
        self.running = True
        print("Agent runtime is live.")
        while self.running:
            if os.getenv("ENABLE_ROUTINES", "1") == "1":
                await self._queue_due_routines()
            await self._process_due_tasks()
            await asyncio.sleep(self.poll_seconds)

    async def _queue_due_routines(self) -> None:
        due_routines = await claim_due_routines(self.db_path)
        for routine in due_routines:
            await create_task(
                self.db_path,
                title=str(routine["name"]),
                details=f"Scheduled routine for {routine['channel']}",
                channel=str(routine["channel"] or "imac"),
                action_type="scheduled_briefing",
                autonomy_mode=str(routine["autonomy_mode"] or "auto_safe"),
                due_at=self._now_iso(),
                payload=str(routine["kind"] or "morning_briefing"),
                priority=3,
            )

    async def _process_due_tasks(self) -> None:
        due_tasks = await claim_due_tasks(self.db_path, self._now_iso())
        resumable = await resumable_running_tasks(self.db_path)
        tasks = {int(task["id"]): task for task in (*resumable, *due_tasks)}
        for task in tasks.values():
            await self._handle_task(task)

    async def _handle_task(self, task: dict[str, str | int | None]) -> None:
        existing_workflow = await get_workflow(self.db_path, int(task["id"]))
        if os.getenv("ENABLE_LANGGRAPH_HARNESS", "1") == "1" and not existing_workflow:
            await self._handle_task_with_harness(task)
            return
        task_id = int(task["id"])
        action_type = str(task["action_type"])
        autonomy_mode = str(task["autonomy_mode"])

        if not self.policy.can_auto_execute(action_type, autonomy_mode):
            await update_task_status(
                self.db_path,
                task_id,
                self.policy.blocked_status(action_type),
                result=self.policy.blocked_reason(action_type),
            )
            await record_task_event(self.db_path, task_id, "blocked", self.policy.blocked_reason(action_type))
            return

        plan = self.planner.build_plan(task)
        workflow = await begin_workflow(self.db_path, task_id, [step.name for step in plan])
        context = dict(workflow.get("context") or {})
        start_at = int(workflow.get("current_step") or 0)
        if start_at == 0:
            await record_task_event(self.db_path, task_id, "plan", ", ".join(step.name for step in plan))
        else:
            await record_task_event(self.db_path, task_id, "resumed", f"Resuming at step {start_at + 1}.")

        try:
            for index, step in enumerate(plan[start_at:], start=start_at):
                await record_task_event(self.db_path, task_id, "step_started", step.name)
                context = await self.executor.execute_step(task, step.name, context)
                passed, detail = self.planner.verify_step(task, step, context)
                if not passed:
                    await record_task_event(self.db_path, task_id, "step_failed", f"{step.name}: {detail}")
                    await finish_workflow(self.db_path, task_id, status="failed", context=context, error=detail)
                    await fail_task(self.db_path, task_id, detail)
                    return
                await save_workflow_progress(self.db_path, task_id, current_step=index + 1, context=context)
                await record_task_event(self.db_path, task_id, "step_passed", f"{step.name}: {detail}")
        except Exception as exc:
            await record_task_event(self.db_path, task_id, "error", str(exc))
            await finish_workflow(self.db_path, task_id, status="failed", context=context, error=str(exc))
            await fail_task(self.db_path, task_id, str(exc))
            return

        await finish_workflow(self.db_path, task_id, status="completed", context=context)
        await complete_task(self.db_path, task_id, result=str(context.get("result") or "Completed."))

    async def _handle_task_with_harness(self, task: dict[str, str | int | None]) -> None:
        task_id = int(task["id"])
        action_type = str(task["action_type"])
        autonomy_mode = str(task["autonomy_mode"])
        if not self.policy.can_auto_execute(action_type, autonomy_mode):
            await update_task_status(
                self.db_path,
                task_id,
                self.policy.blocked_status(action_type),
                result=self.policy.blocked_reason(action_type),
            )
            await record_task_event(self.db_path, task_id, "blocked", self.policy.blocked_reason(action_type))
            return
        await record_task_event(self.db_path, task_id, "harness_started", "LangGraph harness claimed task.")
        try:
            result = await self.harness.run_background_task(task)
        except Exception as exc:
            await record_task_event(self.db_path, task_id, "harness_error", str(exc))
            await fail_task(self.db_path, task_id, str(exc))
            return
        response = str(result.get("final_response") or "Completed.")
        if result.get("pending_approval"):
            await update_task_status(self.db_path, task_id, "awaiting_confirmation", result=response)
            await record_task_event(self.db_path, task_id, "awaiting_confirmation", response)
            return
        await complete_task(self.db_path, task_id, result=response)
        await record_task_event(self.db_path, task_id, "harness_completed", response)

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
