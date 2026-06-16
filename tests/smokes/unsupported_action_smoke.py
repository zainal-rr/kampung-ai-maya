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

import aiosqlite

os.environ.setdefault("MPLCONFIGDIR", "/tmp/kampung-ai-mpl")

from maya_core.assistant import KampungAssistant
from imac_workflows import ImacWorkflowRouter
from lesson_store import init_lesson_db
from routine_store import init_routine_db
from skill_store import init_skill_db
from skill_factory import SkillFactory
from storage import init_db
from web_actions import WebActionRouter


class FakeBridge:
    def open_url(self, url: str, app_name: str = "Google Chrome") -> None:
        self.url = url


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-unsupported-smoke-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)
        assistant = KampungAssistant(db_path=db_path)
        bridge = FakeBridge()
        assistant.commands.web = WebActionRouter(bridge)
        assistant.commands.workflows = ImacWorkflowRouter(db_path, bridge, Path(tmp) / "workspace")

        normal = await assistant.commands.handle("write me a short story", "telegram")
        _require(normal is None, "creative writing should not trigger missing skill")
        workshop = await assistant.commands.handle("Give me an event-day checklist for a small office workshop.", "telegram")
        _require(workshop is None, "workshop checklist should not trigger missing skill through shop substring")

        response = await assistant.handle_text("book me a flight to Penang tomorrow", "telegram")
        lowered = response.lower()
        _require("research" in lowered or "compare" in lowered, "travel request did not offer safe research/comparison")
        _require("before booking" in lowered and "private" in lowered, "flight request did not keep checkout/private-data guard")

        response = await assistant.handle_text("install a random app", "telegram")
        _require("don't have a real skill" in response.lower(), "missing skill prompt did not appear")
        _require("draft the missing skill" in response.lower(), "missing skill prompt did not ask first")

        pending = await _pending_skill_task(db_path)
        _require(pending is not None, "missing skill task was not queued")
        _require("install a random app" in str(pending["payload"]).lower(), "payload did not keep original request")

        declined = await assistant.handle_text("no that is okay", "telegram")
        _require("will not" in declined.lower() or "won't" in declined.lower(), "natural decline was not handled")
        _require(await _pending_skill_task(db_path) is None, "natural decline left skill task pending")

        bare_cancel = await assistant.commands.handle("cancel", "telegram")
        _require("nothing is waiting" in bare_cancel.lower(), "bare cancel should be handled locally")
        _require(await _pending_skill_task(db_path) is None, "bare cancel queued a fake skill task")

        scaffold = await SkillFactory(db_path).scaffold_skill("build a better UI")
        text = Path(scaffold["scaffold_path"]).read_text(encoding="utf-8")
        _require("Learning State" in text and "Activation Checklist" in text, "skill scaffold missing learning lifecycle")
        _require("Permission Boundary" in text and "Tests" in text, "skill scaffold missing safety or tests")

        print("unsupported_action_smoke: ok")


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)


async def _pending_skill_task(db_path: str) -> dict[str, str | int] | None:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT *
            FROM tasks
            WHERE status = 'awaiting_confirmation'
              AND action_type = 'create_skill_scaffold'
            LIMIT 1
            """
        )
        row = await cursor.fetchone()
    return dict(row) if row else None


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
