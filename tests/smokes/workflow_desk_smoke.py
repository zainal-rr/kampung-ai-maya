from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
from pathlib import Path
import tempfile

from maya_core.context_layers import init_context_layers_db
from harness_artifact_store import record_structured_artifact
from harness_models import local_artifact
from harness_store import list_active_runs, upsert_run
from lesson_store import init_lesson_db
from routine_store import init_routine_db
from session_memory_store import init_session_memory_db
from skill_store import init_skill_db
from storage import init_db
from workflow_desk import background_tasks_text, close_matching_workflow, workflow_desk_text


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-workflow-desk-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)
        state = {
            "run_id": "run_ppt",
            "thread_id": "harness:run_ppt",
            "channel": "telegram",
            "workflow_type": "document",
            "goal": "make quantum computing PPT",
            "current_step": 1,
        }
        await upsert_run(db_path, state, status="running")
        file_path = Path(tmp) / "quantum.pptx"
        file_path.write_text("draft", encoding="utf-8")
        await record_structured_artifact(db_path, "run_ppt", local_artifact("presentation", str(file_path), "ppt", "smoke"))
        desk = await workflow_desk_text(db_path)
        _require("quantum computing PPT" in desk, "workflow missing from desk")
        _require(str(file_path) in desk, "latest artifact missing from desk")
        bg = await background_tasks_text(db_path)
        _require("document" in bg, "background workflow missing")
        closed = await close_matching_workflow(db_path, "ppt")
        _require("closed" in closed, "workflow not closed")
        _require(not await list_active_runs(db_path), "workflow still active")
    print("workflow_desk_smoke: ok")


async def _init(db_path: str) -> None:
    for initializer in (
        init_db,
        init_lesson_db,
        init_skill_db,
        init_routine_db,
        init_session_memory_db,
        init_context_layers_db,
    ):
        await initializer(db_path)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
