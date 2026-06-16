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

from skill_memory_store import add_skill_memory, disable_skill_memory, list_skill_memory
from skill_store import init_skill_db, upsert_skill


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-skill-memory-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_skill_db(db_path)
        await upsert_skill(db_path, "flight_search", "Flight Search", "Find flights.", "bounded", "policy", "active", "test")
        ok, _ = await add_skill_memory(
            db_path,
            skill_id="flight_search",
            kind="user_preference",
            content="Preferred airport is KUL.",
            source="explicit",
        )
        _require(ok, "safe skill memory was blocked")
        blocked, message = await add_skill_memory(
            db_path,
            skill_id="flight_search",
            kind="user_preference",
            content="Passport number is A1234567.",
            source="explicit",
        )
        _require(not blocked and "Blocked" in message, "private identifier was not blocked")
        memory = await list_skill_memory(db_path, "flight_search")
        _require(len(memory) == 1 and "KUL" in memory[0]["content"], "skill memory missing")
        count = await disable_skill_memory(db_path, "flight_search", "KUL")
        _require(count == 1, "skill memory was not disabled")
        _require(await list_skill_memory(db_path, "flight_search") == [], "disabled memory leaked")
    print("skill_memory_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
