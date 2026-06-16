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

import aiosqlite

from maya_harness.harness_state import initial_harness_state
from maya_harness.harness_store import init_harness_db, list_active_runs, upsert_run


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-harness-expiry-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_harness_db(db_path)
        old = initial_harness_state(
            run_id="hrn_old",
            thread_id="harness:old",
            channel="telegram",
            user_text="old browser task",
            workflow_type="browser",
        )
        recent = initial_harness_state(
            run_id="hrn_recent",
            thread_id="harness:recent",
            channel="telegram",
            user_text="recent browser task",
            workflow_type="browser",
        )
        paused = initial_harness_state(
            run_id="hrn_paused",
            thread_id="harness:paused",
            channel="telegram",
            user_text="paused approval",
            workflow_type="self_heal",
        )
        await upsert_run(db_path, old, status="running")
        await upsert_run(db_path, recent, status="running")
        await upsert_run(db_path, paused, status="paused")
        async with aiosqlite.connect(db_path) as db:
            await db.execute("UPDATE harness_runs SET updated_at = datetime('now', '-3 hours') WHERE run_id = 'hrn_old'")
            await db.execute("UPDATE harness_runs SET updated_at = datetime('now', '-3 days') WHERE run_id = 'hrn_paused'")
            await db.commit()
        active = await list_active_runs(db_path, "telegram", limit=10)
        active_ids = {run["run_id"] for run in active}
        _require("hrn_old" not in active_ids, "old running workflow was not expired")
        _require("hrn_recent" in active_ids, "recent running workflow was incorrectly expired")
        _require("hrn_paused" in active_ids, "paused approval workflow should remain visible")
        print("harness_store_expiry_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
