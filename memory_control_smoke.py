from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from lesson_store import add_lesson, init_lesson_db
from memory_control import cleanup_stale_memory, forget_memory, memory_sources_text
from session_memory_store import init_session_memory_db, save_session_summary
from storage import get_preference, init_db, upsert_preference


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-memory-control-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        await init_lesson_db(db_path)
        await init_session_memory_db(db_path)
        await upsert_preference(db_path, "pref_dash", "Do not use dash symbols.", source="telegram")
        await add_lesson(db_path, "remember dash", "Do not use dash symbols.", "style", "punctuation", "explicit", "high", "telegram")
        await save_session_summary(db_path, "Shared session summary about context source display")

        sources = await memory_sources_text(db_path, "dash")
        _require("source: telegram" in sources and "confidence: high" in sources, "source display failed")
        forgotten = await forget_memory(db_path, "dash")
        _require("Removed" in forgotten, "forget did not remove matching memory")
        _require(await get_preference(db_path, "pref_dash") is None, "preference was not forgotten")
        cleanup = await cleanup_stale_memory(db_path, keep_summaries=1)
        _require("Preferences and confirmed lessons were left intact" in cleanup, "cleanup guard missing")
        print("memory_control_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
