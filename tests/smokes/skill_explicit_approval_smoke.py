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

from assistant import KampungAssistant
from context_layers import init_context_layers_db
from harness_artifact_store import init_harness_artifact_db
from harness_store import init_harness_db
from lesson_store import init_lesson_db
from memory_service import MemoryService
from routine_store import init_routine_db
from session_memory_store import init_session_memory_db
from skill_registry import SkillRegistry
from skill_store import find_skill, init_skill_db
from storage import create_task, init_db, update_task_status


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-skill-explicit-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)
        stale = await create_task(
            db_path,
            title="Stale self heal approval",
            details="must not be approved by explicit skill scaffold command",
            channel="telegram",
            action_type="self_heal",
        )
        await update_task_status(db_path, stale, "awaiting_confirmation", result="stale approval")

        assistant = KampungAssistant(db_path)
        reply = await assistant.handle_text(
            "approve and scaffold the Stay Ledger skill for Airbnb price capture into travel budgets",
            "telegram",
        )
        _require("created the skill scaffold" in reply.lower(), reply)
        skill = await find_skill(db_path, "stay ledger airbnb price capture into travel budgets")
        _require(skill is not None, "explicit skill scaffold did not create expected skill row")
        _require(Path(str(skill["scaffold_path"])).exists(), "skill scaffold file missing")
        print("skill_explicit_approval_smoke: ok")


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)
    await init_session_memory_db(db_path)
    await init_context_layers_db(db_path)
    await init_harness_db(db_path)
    await init_harness_artifact_db(db_path)
    MemoryService(db_path)
    SkillRegistry(db_path)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
