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
from maya_core.daily_cockpit import daily_cockpit_text, focus_text
from maya_core.lesson_store import init_lesson_db
from maya_core.routine_store import init_routine_db
from maya_core.session_memory_store import init_session_memory_db
from maya_core.skill_store import init_skill_db
from maya_core.storage import create_task, init_db
from maya_core.waiting_on import create_waiting_on
from maya_core.workflow_desk import quiet_mode_text


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-daily-cockpit-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)
        empty = await daily_cockpit_text(db_path, "telegram")
        _require("Nothing urgent" in empty, "empty cockpit should be calm")
        await create_task(db_path, "finish budget draft", channel="telegram")
        await create_waiting_on(db_path, "API keys next Wednesday", "telegram")
        await quiet_mode_text(db_path, "quiet mode on")
        cockpit = await daily_cockpit_text(db_path, "telegram")
        _require("finish budget draft" in cockpit, "task missing from cockpit")
        _require("API keys" in cockpit, "waiting item missing from cockpit")
        _require("Quiet mode is on" in cockpit, "quiet mode missing from cockpit")
        focus = await focus_text(db_path)
        _require("finish budget draft" in focus, "focus did not pick task")
    print("daily_cockpit_smoke: ok")


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
