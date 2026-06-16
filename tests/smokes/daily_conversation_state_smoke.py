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
from lesson_store import add_lesson, init_lesson_db
from route_tracker import last_route_text
from routine_store import init_routine_db
from session_memory_store import init_session_memory_db
from skill_store import init_skill_db
from storage import init_db, upsert_preference, update_task_status
from storage_tasks import create_task


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-daily-state-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)
        assistant = KampungAssistant(db_path)

        await create_task(db_path, "finish Telegram testing", channel="telegram")
        await create_task(db_path, "finish Telegram testing", channel="telegram")
        focus = await assistant.handle_text("what should i focus on today", "telegram")
        _require("finish Telegram testing" in focus, "focus today did not use local cockpit")
        _require(focus.count("finish Telegram testing") == 1, "focus repeated duplicate tasks")
        route = await last_route_text(db_path)
        _require("daily focus" in route, "focus route reason was not specific")

        await upsert_preference(db_path, "last_doc", "/Users/zainal/Desktop/Maya/spreadsheets/telegram.xlsx")
        await upsert_preference(db_path, "pref_short_replies", "short replies", source="telegram")
        await upsert_preference(
            db_path,
            "pref_reply_structure",
            "For structured replies, use 1) for main points and a), b), c) for subpoints.",
            source="telegram",
        )
        await upsert_preference(db_path, "telegram_style", "Keep Telegram replies short and direct.")
        memory = await assistant.handle_text("what do you remember about my Telegram style", "telegram")
        _require("short" in memory.lower(), "Telegram style preference was not returned")
        _require("/Users/" not in memory and ".xlsx" not in memory, "artifact path leaked into preference reply")
        route = await last_route_text(db_path)
        _require("memory lookup" in route, "memory lookup route reason was not specific")

        await add_lesson(db_path, "bad", "you are Maya, you are the one who see", "preference", "global", "explicit", "high", "telegram")
        await add_lesson(db_path, "good", "Keep Telegram replies concise.", "style", "telegram", "explicit", "high", "telegram")
        learned = await assistant.handle_text("what did you learn from me today", "telegram")
        _require("concise" in learned, "good lesson was hidden")
        _require("you are Maya" not in learned, "bad malformed lesson was shown")

        first = await create_task(db_path, "Review Maya self heal proposal", channel="telegram")
        second = await create_task(db_path, "Review Maya self heal proposal", channel="telegram")
        await update_task_status(db_path, first, "awaiting_confirmation")
        await update_task_status(db_path, second, "awaiting_confirmation")
        approvals = await assistant.handle_text("what needs my approval", "telegram")
        _require("tasks #" in approvals, "duplicate task approvals were not grouped")

        print("daily_conversation_state_smoke: ok")


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
