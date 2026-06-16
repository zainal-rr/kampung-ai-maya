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

from assistant import KampungAssistant
from context_layers import init_context_layers_db
from harness_artifact_store import init_harness_artifact_db
from harness_store import init_harness_db
from lesson_store import init_lesson_db
from route_tracker import record_route
from routine_store import init_routine_db
from session_memory_store import init_session_memory_db
from skill_store import init_skill_db
from storage import init_db


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-telegram-text-alias-") as tmp:
        db_path = str(Path(tmp) / "alias.db")
        await _init(db_path)
        old_google = os.environ.get("GOOGLE_API_KEY")
        os.environ.pop("GOOGLE_API_KEY", None)
        try:
            await record_route(db_path, "text", "Gemini Flash text", "normal Telegram text", True)
            reply = await KampungAssistant(db_path).handle_text("show route", "telegram", input_type="text")
            _require("Last route:" in reply, f"show route did not map to /route:\n{reply}")
            _require("normal Telegram text" in reply, f"route payload was not returned:\n{reply}")
            skill_reply = await KampungAssistant(db_path).handle_text(
                "make a proposed skill for PowerPoint visual taste",
                "telegram",
                input_type="text",
            )
            _require("skill scaffold" in skill_reply.lower(), f"PowerPoint skill request was not routed to skill scaffold:\n{skill_reply}")
            _require(".pptx" not in skill_reply.lower(), f"PowerPoint skill request should not create a PPTX:\n{skill_reply}")
            print("telegram_text_alias_smoke: ok")
        finally:
            _restore_env("GOOGLE_API_KEY", old_google)


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)
    await init_session_memory_db(db_path)
    await init_context_layers_db(db_path)
    await init_harness_db(db_path)
    await init_harness_artifact_db(db_path)


def _restore_env(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
