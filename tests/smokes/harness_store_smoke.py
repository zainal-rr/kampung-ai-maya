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

from maya_harness.harness_store import (
    get_active_run,
    init_harness_db,
    latest_events,
    new_run_id,
    record_event,
    upsert_run,
)
from maya_harness.harness_state import initial_harness_state


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def main() -> None:
    with tempfile.NamedTemporaryFile() as tmp:
        db_path = tmp.name
        await init_harness_db(db_path)
        state = initial_harness_state(
            run_id=new_run_id(),
            thread_id="maya:shared",
            channel="telegram",
            user_text="check flight to Penang",
            workflow_type="browser",
        )
        await upsert_run(db_path, state)
        await record_event(db_path, state["run_id"], "test", "store ok")
        active = await get_active_run(db_path, "telegram")
        _require(active is not None, "active run not found")
        _require(active["state"]["workflow_type"] == "browser", "state was not restored")
        events = await latest_events(db_path, state["run_id"])
        _require(events and events[-1]["event"] == "test", "event log missing")
    print("harness_store_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
