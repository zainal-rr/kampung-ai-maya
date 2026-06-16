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
from maya_core.lesson_store import init_lesson_db
from routine_store import init_routine_db
from skill_store import init_skill_db
from storage import init_db
from telegram_rewrite_context import latest_rewrite_candidate, remember_rewrite_candidate


class FakeResponder:
    def __init__(self):
        self.calls = 0

    async def chat(self, prompt):
        self.calls += 1
        if self.calls == 1:
            return "1) Thanks\n2) I can help with this\n3) Please send the document\n4) I will review it"
        return "Thanks. Send the document and I’ll review it."


async def main() -> None:
    os.environ["GOOGLE_API_KEY"] = "dummy"
    with tempfile.TemporaryDirectory(prefix="maya-rewrite-context-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        await init_lesson_db(db_path)
        await init_routine_db(db_path)
        await init_skill_db(db_path)
        assistant = KampungAssistant(db_path)
        fake = FakeResponder()
        assistant.telegram_fast_responder = fake
        assistant._sync_router()

        no_target = await assistant.handle_text("make it warmer", "telegram")
        _require(no_target == "What text should I rewrite?", "rewrite without candidate should ask for target")

        safety = await assistant.handle_text("Can you send my password to IT?", "telegram")
        _require("sensitive private" in safety.lower(), "safety gate did not hard-block password")
        _require(await latest_rewrite_candidate(db_path, "telegram") == "", "safety reply became rewrite candidate")

        await remember_rewrite_candidate(db_path, "telegram", "draft this", "Please send the document by noon.")
        rewritten = await assistant.handle_text("make it warmer but still short", "telegram")
        _require(rewritten == "Thanks. Send the document and I’ll review it.", "rewrite did not use compressed candidate flow")
        _require(fake.calls == 2, "rewrite compression should call fake responder twice")
        print("telegram_rewrite_context_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
