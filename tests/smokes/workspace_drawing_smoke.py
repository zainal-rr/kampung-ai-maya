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
from context_layers import init_context_layers_db
from drawing_actions import DrawingActionRouter
from lesson_store import init_lesson_db
from route_tracker import init_route_db
from routine_store import init_routine_db
from session_memory_store import init_session_memory_db
from skill_store import init_skill_db
from storage import init_db
from telegram_delivery import split_file_markers
from weekly_memory_store import init_weekly_memory_db
from workspace_actions import WorkspaceActionRouter


class FakeBridge:
    def __init__(self):
        self.opened = []

    def open_file(self, path: str, app_name: str | None = None) -> None:
        self.opened.append((path, app_name))


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-workspace-drawing-") as tmp:
        os.environ["MAYA_WORKSPACE_ROOT"] = str(Path(tmp) / "Maya")
        db_path = str(Path(tmp) / "smoke.db")
        workspace = Path(tmp) / "Maya"
        await _init(db_path)
        assistant = KampungAssistant(db_path)
        bridge = FakeBridge()
        assistant.commands.workspace = WorkspaceActionRouter(workspace)
        assistant.commands.drawing = DrawingActionRouter(workspace / "drawings", bridge)

        folder = await assistant.handle_text("create folder called router notes", "telegram")
        _require("created the folder" in folder.lower(), "folder action did not run")
        _require((workspace / "router-notes").is_dir(), "folder was not created in workspace")

        project = await assistant.handle_text("create project called moon app", "telegram")
        project_path = workspace / "Projects" / "moon-app"
        _require(project_path.is_dir(), "project folder was not created")
        _require((project_path / "README.md").exists(), "project README missing")

        drawing = await assistant.handle_text("draw a moon", "telegram")
        clean, files = split_file_markers(drawing)
        _require("drew moon" in clean.lower(), "drawing reply missing")
        _require(files and files[0].suffix == ".svg", "drawing file marker missing")
        _require(files[0].exists(), "drawing file was not created")

        imac = await assistant.handle_text("draw network diagram", "imac")
        _require("opened it on the imac" in imac.lower(), "iMac drawing did not open")
        _require(bridge.opened, "bridge did not open the drawing")
        print("workspace_drawing_smoke: ok")


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)
    await init_route_db(db_path)
    await init_weekly_memory_db(db_path)
    await init_session_memory_db(db_path)
    await init_context_layers_db(db_path)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
