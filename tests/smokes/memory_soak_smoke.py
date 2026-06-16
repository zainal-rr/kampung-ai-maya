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

from maya_core.context_layers import init_context_layers_db, relevant_context_facts
from lesson_store import init_lesson_db
from route_tracker import init_route_db
from routine_store import init_routine_db
from session_compactor import build_session_context, compact_if_needed
from session_memory_store import init_session_memory_db, list_session_summaries
from skill_store import init_skill_db
from storage import get_preference, init_db, save_history_message, upsert_preference


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-memory-soak-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)
        await upsert_preference(db_path, "pref_reply_length", "Keep replies short unless complex.", source="telegram")
        for index in range(90):
            await save_history_message(db_path, 1, "user", _user_turn(index))
            await save_history_message(db_path, 1, "assistant", f"Recorded turn {index}.")
        await save_history_message(
            db_path,
            1,
            "user",
            "Remember that my API key is sk-testsecretvalue1234567890.",
        )
        await save_history_message(db_path, 1, "assistant", "I will not save that sensitive value.")

        result = await compact_if_needed(
            db_path,
            threshold=40,
            token_limit=900,
            token_interval=1,
            keep_recent_tokens=240,
        )
        _require(result.compacted, "long session did not compact")
        summaries = await list_session_summaries(db_path, limit=4)
        _require(summaries, "shared summary was not saved")
        context = await build_session_context(db_path, "telegram imac persistence budget")
        _require("Shared compacted context" in context, "compacted context not injected")
        _require("sk-testsecret" not in context and "API key is" not in context, "sensitive text leaked into compacted context")
        facts = await relevant_context_facts(db_path, "preference api key permission")
        _require(facts, "hard facts were not preserved")
        preference = await get_preference(db_path, "pref_reply_length")
        _require(preference == "Keep replies short unless complex.", "preference was lost")
        print("memory_soak_smoke: ok")


def _user_turn(index: int) -> str:
    anchors = (
        "Remember that Maya should keep Telegram and iMac context connected.",
        "My preference is that important facts stay outside fuzzy summaries.",
        "Do not let quantum advisory override permissions or API key rules.",
        "The active project should persist across normal topic changes.",
    )
    return f"{anchors[index % len(anchors)]} Turn {index} includes router setup, screen sight, and skill testing."


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)
    await init_route_db(db_path)
    await init_session_memory_db(db_path)
    await init_context_layers_db(db_path)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
