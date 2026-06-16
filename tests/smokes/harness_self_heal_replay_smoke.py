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

import maya_harness.harness_tools as harness_tools
from maya_harness.harness_graph import HarnessGraphRunner
from maya_harness.harness_state import initial_harness_state
from maya_harness.harness_store import init_harness_db
from self_heal_store import create_self_heal_report, init_self_heal_db, record_self_heal_stage
from storage import create_task, init_db


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-heal-replay-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        await init_harness_db(db_path)
        await init_self_heal_db(db_path)
        original = harness_tools.HarnessTools._self_heal
        harness_tools.HarnessTools._self_heal = _fake_self_heal
        try:
            state = initial_harness_state(
                run_id="heal_replay",
                thread_id="harness:heal_replay",
                channel="telegram",
                user_text="self heal check",
                workflow_type="self_heal",
            )
            state["user_turn_id"] = "heal_replay:turn"
            await HarnessGraphRunner(db_path).run(state)
            await HarnessGraphRunner(db_path).run(dict(state))
            reports = await _count(db_path, "self_heal_reports")
            tasks = await _count(db_path, "tasks")
            _require(reports == 1, f"duplicate repair reports: {reports}")
            _require(tasks == 1, f"duplicate review tasks: {tasks}")
        finally:
            harness_tools.HarnessTools._self_heal = original
    print("harness_self_heal_replay_smoke: ok")


async def _fake_self_heal(self, text: str, channel: str) -> harness_tools.HarnessToolResult:
    task_id = await create_task(self.db_path, title="Review repair", action_type="apply_code_patch")
    report_id = await create_self_heal_report(
        self.db_path,
        issue="simulated",
        diagnosis="simulated diagnosis",
        proposed_fix="smallest patch",
        tests="targeted smoke",
        task_id=task_id,
    )
    await record_self_heal_stage(self.db_path, report_id, "proposed", "smallest patch")
    return harness_tools.HarnessToolResult("completed", f"Created repair report #{report_id}", next_step="self_heal")


async def _count(db_path: str, table: str) -> int:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(f"SELECT COUNT(*) FROM {table}")
        row = await cursor.fetchone()
    return int(row[0])


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
