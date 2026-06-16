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

from maya_core.lesson_store import add_lesson, init_lesson_db
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
        await upsert_preference(db_path, "maya_browser_workflow", '{"goal":"flight test"}', source="workflow")
        await upsert_preference(db_path, "maya_last_document_path", "/Users/example/Desktop/Maya/file.docx", source="document")
        await upsert_preference(db_path, "visible_screen", "visible: screen visible", source="screen")
        await upsert_preference(db_path, "travel_state", '{"destination":"Seoul"}', source="travel")
        await upsert_preference(db_path, "bad_timestamp", "1970-01-01T00:00:00+00:00", source="telegram")
        await upsert_preference(db_path, "camera_visible", "visible: Cisco Desk Camera 4K frame visible.", source="vision")
        filtered_sources = await memory_sources_text(db_path)
        _require("flight test" not in filtered_sources, "workflow JSON leaked into memory sources")
        _require("file.docx" not in filtered_sources, "document path leaked into memory sources")
        _require("visible: screen visible" not in filtered_sources, "screen state leaked into memory sources")
        _require("Seoul" not in filtered_sources, "travel JSON leaked into memory sources")
        _require("1970-01-01" not in filtered_sources, "timestamp sentinel leaked into memory sources")
        _require("Cisco Desk Camera" not in filtered_sources, "vision state leaked into memory sources")
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
