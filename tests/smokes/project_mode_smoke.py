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

from maya_core.assistant import KampungAssistant
from lesson_store import init_lesson_db
from project_store import active_project, build_project_context
from routine_store import init_routine_db
from session_memory_store import init_session_memory_db
from skill_store import init_skill_db
from storage import init_db


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-project-mode-") as tmp:
        root = Path(tmp) / "projects"
        project = root / "orchid-lab"
        project.mkdir(parents=True)
        os.environ["MAYA_PROJECT_ROOTS"] = str(root)
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)

        assistant = KampungAssistant(db_path)
        opened = await assistant.handle_text("open project Orchid Lab", "telegram")
        _require("opened project orchid-lab" in opened.lower(), "project did not open")
        active = await active_project(db_path)
        _require(active is not None and active.path == project.resolve(), "active project did not persist")

        status = await assistant.handle_text("what project are we in", "telegram")
        _require("orchid-lab" in status and str(project.resolve()) in status, "project status failed")
        readme = await assistant.handle_text("make a README for this project", "telegram")
        _require("created README.md" in readme and (project / "README.md").exists(), "README was not created")

        await assistant.handle_text("new topic", "telegram")
        still_active = await active_project(db_path)
        _require(still_active is not None and still_active.path == project.resolve(), "new topic closed project")
        context = await build_project_context(db_path, "what next")
        _require("Active project context:" in context and "created_file" in context, "project context missing notes")

        closed = await assistant.handle_text("close project", "telegram")
        _require("closed the active project" in closed.lower(), "project did not close")
        _require(await active_project(db_path) is None, "active project remained after close")
        print("project_mode_smoke: ok")


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)
    await init_session_memory_db(db_path)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
