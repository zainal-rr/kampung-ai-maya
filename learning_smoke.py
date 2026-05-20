from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/kampung-ai-mpl")

from assistant import KampungAssistant
from lesson_store import init_lesson_db, list_lessons
from memory_service import MemoryService
from routine_store import init_routine_db
from skill_store import init_skill_db
from storage import init_db, list_preferences


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-learning-smoke-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)
        assistant = KampungAssistant(db_path=db_path)

        explicit = await assistant.handle_text(
            "My preference is short Telegram replies unless it is a complex task",
            "telegram",
        )
        _require("saved" in explicit.lower(), "explicit lesson was not saved")

        implicit = await assistant.handle_text("that sounds too formal", "telegram")
        _require("do you want me to save it" in implicit.lower(), "implicit lesson did not ask first")

        confirmed = await assistant.handle_text("yes", "telegram")
        _require("saved" in confirmed.lower(), "confirmed lesson was not saved")

        inspected = await assistant.handle_text("what did you learn from me today", "telegram")
        _require("short telegram replies" in inspected.lower(), "lesson inspection missed explicit rule")
        _require("less formal" in inspected.lower(), "lesson inspection missed confirmed rule")

        bundled = await assistant.handle_text(
            "1) what did you learn from me today\n2) tell me my preference",
            "telegram",
        )
        _require("short telegram replies" in bundled.lower(), "bundled lesson route missed explicit rule")
        _require("less formal" in bundled.lower(), "bundled lesson route missed confirmed rule")

        preferences = await list_preferences(db_path, limit=10)
        lessons = await list_lessons(db_path, limit=10)
        context = await MemoryService(db_path).build_prompt_context("keep Telegram replies short")
        _require(len(preferences) >= 2, "preferences were not written")
        _require(len(lessons) >= 2, "lessons were not logged")
        _require("short telegram replies" in context.lower(), "retrieval did not include saved preference")

        print("learning_smoke: ok")
        print(f"preferences: {len(preferences)}")
        print(f"lessons: {len(lessons)}")


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
