from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import os
import tempfile
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/kampung-ai-mpl")

from maya_core.assistant import KampungAssistant
from maya_core.assistant_commands import AssistantCommandRouter
from maya_core.lesson_store import init_lesson_db
from maya_memory.memory_service import MemoryService
from maya_core.routine_store import init_routine_db
from skill_registry import SkillRegistry
from skill_store import init_skill_db
from storage import init_db


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-task-smoke-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)
        router = AssistantCommandRouter(db_path, MemoryService(db_path), SkillRegistry(db_path))

        created = await router.handle("create task remind me to check hosting renewal tomorrow", "telegram")
        _require(created and "saved task" in created.lower(), "task was not created")

        listed = await router.handle("what are my tasks", "telegram")
        _require(listed and "hosting renewal" in listed.lower(), "created task was not listed")

        deleted = await router.handle("delete my tasks to check the hosting renewal tomorrow", "telegram")
        _require(deleted and "removed task" in deleted.lower(), "task was not deleted")

        empty = await router.handle("what are my tasks", "telegram")
        _require(empty == "You don't have any open tasks right now.", "deleted task still appears open")

        assistant = KampungAssistant(db_path=db_path)
        await assistant.handle_text("1) what did you learn from me today\n2) tell me my preference", "telegram")
        await assistant.handle_text("create task remind me to check hosting renewal tomorrow", "telegram")
        reply = await assistant.handle_text("delete my tasks to check the hosting renewal tomorrow", "telegram")
        lowered = reply.lower()
        _require("removed task" in lowered, "assistant did not delete task through full path")
        _require("preference" not in lowered, "delete reply leaked old preference answer")
        _require("learned today" not in lowered, "delete reply leaked old learning answer")

        print("task_smoke: ok")


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
