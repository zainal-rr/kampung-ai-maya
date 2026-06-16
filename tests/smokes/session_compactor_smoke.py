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
from context_layers import init_context_layers_db
from lesson_store import init_lesson_db
from route_tracker import init_route_db
from routine_store import init_routine_db
from session_compactor import build_session_context, compact_if_needed, inspect_session_context
from session_memory_store import init_session_memory_db, latest_session_summary
from skill_store import init_skill_db
from storage import init_db, save_history_message
from weekly_memory_store import init_weekly_memory_db


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-session-context-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)
        await _seed_history(db_path)

        result = await compact_if_needed(
            db_path,
            threshold=200,
            token_limit=450,
            token_interval=1,
            keep_recent_tokens=180,
        )
        _require(result.compacted, "history did not compact")
        _require(result.token_count >= 450, "token budget did not trigger compaction")
        summary = await latest_session_summary(db_path)
        _require(summary is not None, "summary was not saved")
        _require("context" in str(summary["summary"]).lower(), "summary missed context topic")

        context = await build_session_context(db_path, "telegram imac context continuity")
        _require("Shared compacted context" in context, "prompt context was not built")
        _require("Hard facts and rules" in context, "hard fact layer was not injected")
        check_in_context = await build_session_context(db_path, "are you there")
        _require("Shared compacted context" not in check_in_context, "check-ins should not inherit compacted summaries")
        inspected = await inspect_session_context(db_path)
        _require("Context window:" in inspected, "inspection reply missing header")

        assistant = KampungAssistant(db_path)
        reply = await assistant.handle_text("show context window", "imac")
        _require("Context window:" in reply, "assistant did not expose context command")
        print("session_compactor_smoke: ok")


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)
    await init_route_db(db_path)
    await init_weekly_memory_db(db_path)
    await init_session_memory_db(db_path)
    await init_context_layers_db(db_path)


async def _seed_history(db_path: str) -> None:
    turns = [
        "I want Maya to remember context across Telegram and iMac.",
        "The context window should behave like Codex compaction.",
        "Keep the compacted context shared between channels.",
        "Add a command so I can inspect the carried context.",
        "Quantum ideas are only advisory and behind a flag.",
        "LangGraph can help orchestration but local storage owns memory.",
        "The new summary should not bring back old archive lore.",
        "Make sure this works before the API key arrives.",
        "I am testing whether Maya stays persistent.",
        "The iMac and Telegram should feel like one Maya.",
        "Context should survive when I switch channels.",
        "Use the latest compacted context before answering.",
        "Do not let advisory experiments override routes.",
        "Make the context inspectable without using provider keys.",
        "Remember that separate topic threads should preserve hard facts apart from vibes.",
        "My preference is that important facts stay outside fuzzy summaries.",
        "I want Maya to keep context longer before compacting.",
    ]
    for text in turns:
        await save_history_message(db_path, 1, "user", text)
        await save_history_message(db_path, 1, "assistant", f"Recorded: {text}")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
