from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
from pathlib import Path
import tempfile

from maya_core.context_layers import init_context_layers_db
from maya_core.lesson_store import init_lesson_db
from maya_core.routine_store import init_routine_db
from maya_core.session_memory_store import init_session_memory_db
from maya_core.skill_store import init_skill_db
from maya_core.storage import init_db
from maya_core.waiting_on import handle_waiting_on, list_waiting_on


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-waiting-on-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)
        created = await handle_waiting_on(db_path, "I am waiting on API keys next Wednesday", "telegram")
        _require(created and "tracking waiting-on" in created, "waiting-on item not created")
        items = await list_waiting_on(db_path)
        _require(items and "API keys" in str(items[0]["title"]), "waiting-on item not listed")
        listed = await handle_waiting_on(db_path, "what am I waiting on", "telegram")
        _require(listed and "API keys" in listed, "waiting-on list reply wrong")
        cleared = await handle_waiting_on(db_path, "clear waiting on API keys", "telegram")
        _require(cleared and "cleared" in cleared, "waiting-on item not cleared")
        _require(not await list_waiting_on(db_path), "waiting-on item still active")
    print("waiting_on_smoke: ok")


async def _init(db_path: str) -> None:
    for initializer in (
        init_db,
        init_lesson_db,
        init_skill_db,
        init_routine_db,
        init_session_memory_db,
        init_context_layers_db,
    ):
        await initializer(db_path)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
