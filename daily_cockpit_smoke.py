from __future__ import annotations

import asyncio
from pathlib import Path
import tempfile

from context_layers import init_context_layers_db
from daily_cockpit import daily_cockpit_text, focus_text
from lesson_store import init_lesson_db
from routine_store import init_routine_db
from session_memory_store import init_session_memory_db
from skill_store import init_skill_db
from storage import create_task, init_db
from waiting_on import create_waiting_on
from workflow_desk import quiet_mode_text


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
