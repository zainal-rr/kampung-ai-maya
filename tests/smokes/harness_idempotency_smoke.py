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

import maya_harness.harness_tools as harness_tools
from maya_harness.harness_graph import HarnessGraphRunner
from maya_harness.harness_state import initial_harness_state
from maya_harness.harness_store import init_harness_db
from maya_core.storage import init_db


CALLS = 0


async def fake_general(self, text: str, channel: str):
    global CALLS
    CALLS += 1
    return harness_tools.HarnessToolResult("completed", f"side effect {CALLS}", next_step="fake")


async def main() -> None:
    for _ in range(3):
        await _case()
    print("harness_idempotency_smoke: ok")


async def _case() -> None:
    global CALLS
    CALLS = 0
    original = harness_tools.HarnessTools._general
    harness_tools.HarnessTools._general = fake_general
    try:
        with tempfile.NamedTemporaryFile() as tmp:
            db_path = tmp.name
            await init_db(db_path)
            await init_harness_db(db_path)
            state = initial_harness_state(
                run_id="idem_run",
                thread_id="harness:idem_run",
                channel="telegram",
                user_text="do stable side effect",
                workflow_type="general",
            )
            runner = HarnessGraphRunner(db_path)
            first = await runner.run(state)
            second = await runner.run(state)
            _require(first["final_response"] == "side effect 1", "first execution failed")
            _require(second["final_response"] == "side effect 1", "cached result missing")
            _require(CALLS == 1, "side effect repeated")
    finally:
        harness_tools.HarnessTools._general = original


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
