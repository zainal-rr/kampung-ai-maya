from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from lesson_store import init_lesson_db
from routine_store import init_routine_db
from screen_responder import ScreenResponder
from screen_session import activate_screen_sight
from skill_store import init_skill_db
from storage import init_db
from utils import OSBridge


async def main() -> None:
    question = " ".join(sys.argv[1:]).strip() or "Can you see what i open in chrome?"
    with tempfile.TemporaryDirectory(prefix="maya-screen-answer-") as tmp:
        db_path = str(Path(tmp) / "probe.db")
        await _init(db_path)
        await activate_screen_sight(db_path)
        answer = await ScreenResponder(db_path).handle(question, "telegram")
        print("== Kampung AI Screen Answer Probe ==")
        print(f"question: {question}")
        print(answer)
    try:
        OSBridge().switch_app("Codex")
    except Exception:
        pass


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)


if __name__ == "__main__":
    asyncio.run(main())
