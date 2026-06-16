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

import harness_tools
from harness_router import HarnessRouter
from harness_store import init_harness_db, latest_events
from storage import init_db


async def fake_screen(self, text: str, channel: str):
    return harness_tools.HarnessToolResult("completed", "I see it. Fake screen response.")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def main() -> None:
    original = harness_tools.HarnessTools._screen
    harness_tools.HarnessTools._screen = fake_screen
    try:
        with tempfile.NamedTemporaryFile() as tmp:
            db_path = tmp.name
            await init_db(db_path)
            await init_harness_db(db_path)
            router = HarnessRouter(db_path)
            reply = await router.handle("look at my screen", "telegram")
            _require(reply == "I see it. Fake screen response.", "screen workflow did not answer")
            events = await latest_events(db_path, "hrn_missing")
            _require(events == [], "unexpected events for missing run")
    finally:
        harness_tools.HarnessTools._screen = original
    print("harness_screen_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
