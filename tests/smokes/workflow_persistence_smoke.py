from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import tempfile
from pathlib import Path

from maya_core.agent_runtime import AgentRuntime
from maya_core.lesson_store import init_lesson_db
from routine_store import init_routine_db
from route_tracker import init_route_db
from skill_store import init_skill_db
from storage import create_task, init_db, list_tasks, record_task_event
from storage_tasks import update_task_status
from weekly_memory_store import init_weekly_memory_db
from workflow_store import begin_workflow, get_workflow, init_workflow_db, save_workflow_progress


class FakeExecutor:
    def __init__(self):
        self.steps: list[str] = []

    async def execute_step(self, task, step_name, context):
        self.steps.append(step_name)
        if step_name == "prepare_message":
            raise AssertionError("resume should skip already completed prepare step")
        if step_name == "deliver_message":
            context["delivered"] = True
            context["result"] = "resumed delivery"
            return context
        raise AssertionError(f"unexpected step {step_name}")


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-workflow-resume-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)
        task_id = await create_task(db_path, "resume reminder", action_type="follow_up", autonomy_mode="auto_safe")
        await update_task_status(db_path, task_id, "running")
        await begin_workflow(db_path, task_id, ["prepare_message", "deliver_message"])
        await save_workflow_progress(db_path, task_id, current_step=1, context={"message": "resume reminder"})
        await record_task_event(db_path, task_id, "simulated_crash", "crash after prepare_message")

        tasks = await list_tasks(db_path, statuses=("running",), limit=1)
        runtime = AgentRuntime(db_path)
        runtime.executor = FakeExecutor()
        await runtime._handle_task(tasks[0])

        workflow = await get_workflow(db_path, task_id)
        completed = await list_tasks(db_path, statuses=("completed",), limit=1)
        _require(runtime.executor.steps == ["deliver_message"], "runtime did not resume from saved step")
        _require(workflow and workflow["status"] == "completed", "workflow did not complete")
        _require(completed and completed[0]["result"] == "resumed delivery", "task did not complete")
        print("workflow_persistence_smoke: ok")


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)
    await init_route_db(db_path)
    await init_weekly_memory_db(db_path)
    await init_workflow_db(db_path)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
