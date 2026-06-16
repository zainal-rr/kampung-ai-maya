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

import maya_browser.browser_control as browser_control
from maya_harness.harness_router import HarnessRouter
from maya_harness.harness_store import get_active_run, init_harness_db
from maya_core.storage import init_db


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def main() -> None:
    original = browser_control.BrowserController.open_search
    browser_control.BrowserController.open_search = lambda self, query: None
    try:
        with tempfile.NamedTemporaryFile() as tmp:
            db_path = tmp.name
            await init_db(db_path)
            await init_harness_db(db_path)
            router = HarnessRouter(db_path)
            reply = await router.handle("check flight to Penang tomorrow", "telegram")
            _require(reply and "flight" in reply.lower(), "browser workflow did not start")
            active = await get_active_run(db_path, "telegram")
            _require(active and active["workflow_type"] == "browser", "browser workflow should stay resumable")
    finally:
        browser_control.BrowserController.open_search = original
    print("harness_browser_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
