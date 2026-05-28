from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from lesson_store import add_lesson, init_lesson_db
from memory_control import cleanup_stale_memory, forget_memory, memory_sources_text
from session_search import index_session_message, search_sessions
from session_memory_store import init_session_memory_db, save_session_summary
from storage import get_history, get_preference, init_db, save_history_message, upsert_preference


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-memory-control-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        await init_lesson_db(db_path)
        await init_session_memory_db(db_path)
        await upsert_preference(db_path, "pref_dash", "Do not use dash symbols.", source="telegram")
        await add_lesson(db_path, "remember dash", "Do not use dash symbols.", "style", "punctuation", "explicit", "high", "telegram")
        await save_session_summary(db_path, "Shared session summary about context source display")
        await save_history_message(db_path, 1, "user", "remember dash forever", "telegram")

        sources = await memory_sources_text(db_path, "dash")
        _require("source: telegram" in sources and "confidence: high" in sources, "source display failed")
        forgotten = await forget_memory(db_path, "dash")
        _require("Removed" in forgotten, "forget did not remove matching memory")
        _require("raw conversation turns: 1" in forgotten, "forget did not report raw history deletion")
        _require(await get_preference(db_path, "pref_dash") is None, "preference was not forgotten")
        _require(not await search_sessions(db_path, "dash"), "session search row was not forgotten")
        _require(not any("dash" in row["content"] for row in await get_history(db_path, 1, 5)), "history row was not forgotten")
        await upsert_preference(db_path, "lesson_global_my_regression_fruit_is_rambutan", "my regression fruit is rambutan", source="telegram")
        await add_lesson(
            db_path,
            "Remember that my regression fruit is rambutan",
            "my regression fruit is rambutan",
            "preference",
            "global",
            "explicit",
            "high",
            "telegram",
        )
        fuzzy = await forget_memory(db_path, "rambutan is my regression fruit")
        _require("Removed" in fuzzy, "reordered forget query did not remove memory")
        _require(await get_preference(db_path, "lesson_global_my_regression_fruit_is_rambutan") is None, "fuzzy forget did not remove preference")
        await upsert_preference(db_path, "lesson_global_my_regression_fruit_is_rambutan", "my regression fruit is rambutan", source="telegram")
        await save_history_message(db_path, 1, "user", "What is my regression fruit?", "telegram")
        await save_history_message(db_path, 1, "assistant", "It's rambutan.", "telegram")
        await index_session_message(db_path, "user", "What is my regression fruit?", "telegram")
        await index_session_message(db_path, "assistant", "It's rambutan.", "telegram")
        adjacent = await forget_memory(db_path, "my regression fruit")
        _require("Removed" in adjacent, "forget did not remove adjacent recall context")
        _require(await get_preference(db_path, "lesson_global_my_regression_fruit_is_rambutan") is None, "adjacent forget did not remove preference")
        _require(not any("rambutan" in row["content"].lower() for row in await get_history(db_path, 1, 10)), "adjacent assistant answer survived history forget")
        _require(not any("rambutan" in row["content"].lower() for row in await search_sessions(db_path, "rambutan", 10)), "adjacent assistant answer survived search forget")
        await upsert_preference(db_path, "lesson_global_my_regression_fruit_is_rambutan", "my regression fruit is rambutan", source="telegram")
        await save_history_message(db_path, 1, "assistant", "It's rambutan.", "telegram")
        await index_session_message(db_path, "assistant", "It's rambutan.", "telegram")
        orphan = await forget_memory(db_path, "my regression fruit")
        _require("Removed" in orphan, "forget did not remove orphan recall context")
        _require(not any("rambutan" in row["content"].lower() for row in await get_history(db_path, 1, 10)), "orphan assistant answer survived history forget")
        _require(not any("rambutan" in row["content"].lower() for row in await search_sessions(db_path, "rambutan", 10)), "orphan assistant answer survived search forget")
        cleanup = await cleanup_stale_memory(db_path, keep_summaries=1)
        _require("Preferences and confirmed lessons were left intact" in cleanup, "cleanup guard missing")
        print("memory_control_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
