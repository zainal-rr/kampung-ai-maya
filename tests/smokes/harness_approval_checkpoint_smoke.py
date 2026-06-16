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

from maya_harness.harness_router import HarnessRouter
from maya_harness.harness_store import get_active_run, init_harness_db
from storage import init_db


async def main() -> None:
    for _ in range(3):
        await _case()
    print("harness_approval_checkpoint_smoke: ok")


async def _case() -> None:
    with tempfile.NamedTemporaryFile() as tmp:
        db_path = tmp.name
        await init_db(db_path)
        await init_harness_db(db_path)
        router = HarnessRouter(db_path)
        first = await router.handle("book flight to Penang tomorrow", "telegram")
        _require(first and "confirmation" in first.lower(), "approval did not pause")
        active = await get_active_run(db_path, "telegram")
        snapshot = await router.runner.get_snapshot(active)
        _require(snapshot.get("graph_status") == "waiting_approval", "checkpoint not waiting approval")
        approved = await HarnessRouter(db_path).handle("yes", "telegram")
        _require(approved is not None, "approval resume failed")
        second_yes = await HarnessRouter(db_path).handle("yes", "telegram")
        _require(second_yes is None, "second yes should not re-execute")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
