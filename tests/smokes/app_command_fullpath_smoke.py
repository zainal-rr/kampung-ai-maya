from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from assistant import KampungAssistant
from lesson_store import init_lesson_db
from local_actions import LocalActionRouter
from routine_store import init_routine_db
from skill_store import init_skill_db
from storage import init_db


class FakeBridge:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def switch_app(self, name: str) -> None:
        self.calls.append(("switch", name))

    def get_frontmost_app(self) -> str:
        return self.calls[-1][1]


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-app-fullpath-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)
        bridge = FakeBridge()
        assistant = KampungAssistant(db_path=db_path)
        assistant.commands.actions = LocalActionRouter(bridge)

        first = await assistant.handle_text("Maya open my chrome", "telegram")
        _require("Google Chrome" in first, "Maya-prefixed app command failed")
        second = await assistant.handle_text("open it in my imac", "telegram")
        _require("Google Chrome" in second, "pronoun app command failed")
        third = await assistant.handle_text("can you open my browser please", "telegram")
        _require("Google Chrome" in third, "browser alias full path failed")
        where = await assistant.handle_text("where?", "telegram")
        _require("Google Chrome" in where, "where follow-up full path failed")
        _require(bridge.calls == [
            ("switch", "Google Chrome"),
            ("switch", "Google Chrome"),
            ("switch", "Google Chrome"),
        ], "full path switched to the wrong app")
        print("app_command_fullpath_smoke: ok")


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
