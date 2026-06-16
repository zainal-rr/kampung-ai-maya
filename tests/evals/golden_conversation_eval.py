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

from maya_core.assistant import KampungAssistant
from maya_core.context_layers import init_context_layers_db
from maya_core.lesson_store import init_lesson_db
from maya_core.route_tracker import init_route_db
from maya_core.routine_store import init_routine_db
from session_memory_store import init_session_memory_db, save_session_summary
from skill_store import init_skill_db
from storage import init_db
from telegram_commands import command_to_text, parse_command
from weekly_memory_store import init_weekly_memory_db
from workflow_store import init_workflow_db


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-golden-eval-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)
        maya = KampungAssistant(db_path)

        await _case(maya, "hello maya", "Hey. I'm here", "greeting")
        saved = await maya.handle_text("My preference is no exclamation marks", "telegram")
        _require("saved" in saved.lower(), "preference save failed")
        prefs = await maya.handle_text("tell me my preference", "telegram")
        _require("exclamation" in prefs.lower() and "!" not in prefs, "preference retrieval failed")
        await save_session_summary(db_path, "Shared session summary about persistence across Telegram and iMac")
        context = await maya.handle_text("show context window", "telegram")
        _require("Context window:" in context and "persistence" in context, "context inspection failed")
        task = await maya.handle_text("remind me to check hosting tomorrow", "telegram")
        _require("saved task" in task.lower(), "task capture failed")
        mapped = await command_to_text(db_path, parse_command("/complex think through architecture"))
        _require(mapped == "[complex]think through architecture", "complex command mapping failed")
        print("golden_conversation_eval: ok")


async def _case(maya: KampungAssistant, text: str, expected: str, label: str) -> None:
    reply = await maya.handle_text(text, "telegram")
    _require(expected in reply, f"{label} failed: {reply}")


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)
    await init_route_db(db_path)
    await init_weekly_memory_db(db_path)
    await init_session_memory_db(db_path)
    await init_context_layers_db(db_path)
    await init_workflow_db(db_path)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
