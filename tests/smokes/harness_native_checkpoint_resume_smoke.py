from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import json
import tempfile

import maya_harness.harness_tools as harness_tools
from maya_harness.harness_router import HarnessRouter
from maya_harness.harness_store import get_active_run, init_harness_db
from maya_core.storage import init_db


async def fake_screen(self, text: str, channel: str):
    return harness_tools.HarnessToolResult("completed", f"checkpoint screen: {text}", next_step="screen", keep_open=True)


async def main() -> None:
    for _ in range(3):
        await _case()
    print("harness_native_checkpoint_resume_smoke: ok")


async def _case() -> None:
    original = harness_tools.HarnessTools._screen
    harness_tools.HarnessTools._screen = fake_screen
    try:
        with tempfile.NamedTemporaryFile() as tmp:
            db_path = tmp.name
            await init_db(db_path)
            await init_harness_db(db_path)
            router = HarnessRouter(db_path)
            first = await router.handle("look at my screen", "telegram")
            _require(first == "checkpoint screen: look at my screen", "screen start failed")
            active = await get_active_run(db_path, "telegram")
            _require(active and active["thread_id"].startswith("harness:"), "unique harness thread missing")
            await _poison_state_json(db_path, active["run_id"])
            second = await HarnessRouter(db_path).handle("what about now", "telegram")
            _require(second == "checkpoint screen: what about now", "resume did not use checkpoint state")
    finally:
        harness_tools.HarnessTools._screen = original


async def _poison_state_json(db_path: str, run_id: str) -> None:
    import aiosqlite

    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE harness_runs SET state_json = ? WHERE run_id = ?",
            (json.dumps({"run_id": "wrong", "workflow_type": "wrong", "user_text": "poison"}), run_id),
        )
        await db.commit()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
