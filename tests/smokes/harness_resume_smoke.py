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
from maya_core.storage import init_db


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def main() -> None:
    with tempfile.NamedTemporaryFile() as tmp:
        db_path = tmp.name
        await init_db(db_path)
        await init_harness_db(db_path)
        router = HarnessRouter(db_path)
        first = await router.handle("book flight to Penang tomorrow", "telegram")
        _require(first and "confirmation" in first.lower(), "sensitive click did not pause")
        active = await get_active_run(db_path, "telegram")
        _require(active and active["status"] == "paused", "paused run missing")
        second = await HarnessRouter(db_path).handle("no", "telegram")
        _require(second and "won't do" in second.lower(), "decline did not cancel")
        bypass = await router.handle("open the last document", "telegram")
        _require(bypass is None, "latest document command should bypass harness and reach command router")
        recall_bypass = await router.handle("what document did you just create?", "telegram")
        _require(recall_bypass is None, "recent document recall should bypass harness and reach command router")
        just_now_bypass = await router.handle("what document did you create just now?", "telegram")
        _require(just_now_bypass is None, "just-now recent document recall should bypass harness and reach command router")
        typed_bypass = await router.handle("open PowerPoint Kampung AI Telegram features", "telegram")
        _require(typed_bypass is None, "typed file-open command should bypass harness and reach file opener")
    print("harness_resume_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
