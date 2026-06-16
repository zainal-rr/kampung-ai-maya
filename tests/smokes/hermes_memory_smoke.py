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

from curated_memory import (
    CORE_SCOPE,
    PROFILE_SCOPE,
    add_curated_memory,
    curated_memory_status,
    init_curated_memory_db,
    scope_summary,
)
from assistant import KampungAssistant
from session_memory_actions import handle_session_memory_command, save_voice_session_summary
from session_search import init_session_search_db, search_sessions
from storage import init_db, save_history_message


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-hermes-memory-") as tmp:
        db_path = f"{tmp}/memory.sqlite"
        await init_db(db_path)
        await init_curated_memory_db(db_path)
        await init_session_search_db(db_path)

        ok, _ = await add_curated_memory(db_path, "I prefer short Telegram replies")
        _require(ok, "profile memory not saved")
        profile = await scope_summary(db_path, PROFILE_SCOPE)
        _require(profile["cap"] == 1499, "profile cap mismatch")

        ok, _ = await add_curated_memory(db_path, "Kampung AI uses Option Space for iMac voice and no wake activation")
        _require(ok, "core memory not saved")
        core = await scope_summary(db_path, CORE_SCOPE)
        _require(core["cap"] == 2477, "core cap mismatch")

        await save_history_message(db_path, 1, "user", "Travel testing happens from Telegram while away.")
        rows = await search_sessions(db_path, "travel testing")
        _require(rows, "session search missed saved history")

        await save_voice_session_summary(db_path, ["Remember that today we are testing full Kampung AI readiness."])
        rows = await search_sessions(db_path, "readiness")
        _require(rows, "voice session was not indexed")

        reply = await handle_session_memory_command(db_path, "save this conversation for memory")
        _require(reply and "Saved session memory" in reply, "manual session save failed")
        status = await curated_memory_status(db_path)
        _require("2477" in status and "1499" in status, "memory status missing caps")
        maya = KampungAssistant(db_path)
        await maya._maybe_curate_memory("should I put this note in the deck?", "telegram")
        profile_after_question = await scope_summary(db_path, PROFILE_SCOPE)
        _require(
            "should I put this note" not in str(profile_after_question["summary"]),
            "generic should-question was saved as curated memory",
        )

    print("hermes_memory_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
