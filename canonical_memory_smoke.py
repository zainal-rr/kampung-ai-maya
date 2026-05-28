from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from canonical_memory import search_canonical_direct_fact
from learning_pipeline import LearningPipeline
from lesson_store import init_lesson_db
from memory_control import forget_memory
from memory_service import MemoryService
from storage import init_db


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-canonical-memory-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        await init_lesson_db(db_path)
        learned = await LearningPipeline(db_path).handle("remember that my telegram test drink is teh ais", "telegram")
        _require(learned and "saved" in learned.lower(), "explicit memory was not saved")
        direct = await MemoryService(db_path).search_direct_fact("what is my telegram test drink")
        _require(direct == ["my telegram test drink is teh ais"], "canonical direct recall failed")
        canonical = await search_canonical_direct_fact(db_path, "my telegram test drink")
        _require(canonical == ["my telegram test drink is teh ais"], "canonical store did not return fact")
        forgotten = await forget_memory(db_path, "my telegram test drink")
        _require("canonical memory: 1" in forgotten, "forget did not mark canonical memory")
        after = await MemoryService(db_path).search_direct_fact("what is my telegram test drink")
        _require(after == [], "forgotten canonical memory leaked into recall")
    print("canonical_memory_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
