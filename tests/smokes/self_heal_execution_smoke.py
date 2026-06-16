from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import os
import re
import tempfile
from pathlib import Path

import aiosqlite

from assistant_model_lanes import ModelLanes
from harness_router import HarnessRouter
from harness_store import get_run, init_harness_db, latest_events
from self_heal_store import latest_self_heal_report
from storage import init_db


class FakeMind:
    async def chat(self, _messages, reasoning_effort=None):
        return (
            "Summary\n"
            "Concrete failure identified: core memory saturation and memory leak risk.\n"
            "Key Changes\n"
            "Add memory canary proof and checkpointed self heal.\n"
            "Test Plan\n"
            "Run memory audit smoke and self heal execution smoke."
        )


class FakeSteward:
    async def chat(self, _messages):
        return "PASS: safe if snapshot happens before mutation and restart remains separate approval."


class FakePremiumSight:
    async def chat(self, _messages):
        return "Research context"


async def main() -> None:
    await _approval_and_resume()
    await _decline_cancels()
    await _verification_failure_report()
    print("self_heal_execution_smoke: ok")


async def _approval_and_resume() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-self-heal-exec-") as tmp:
        db_path = await _db(tmp)
        reply = await _complex_reply(db_path)
        run_id = _run_id(reply)
        router = HarnessRouter(db_path)
        checkpointed = await router.handle("yes", "telegram")
        _require(checkpointed and "Self-heal workflow checkpointed" in checkpointed, "first approval did not checkpoint")
        run = await get_run(db_path, run_id)
        checkpoint = run["state"].get("self_heal_checkpoint")
        _require(run["status"] == "paused", "run should pause for isolated mutation approval")
        _require(Path(checkpoint["snapshot_dir"]).exists(), "workflow snapshot missing")
        _require(Path(checkpoint["memory_rollback_snapshot"]).exists(), "memory rollback snapshot missing")
        _require(await _canary_count(db_path) == 0, "mutation happened before second approval")
        final = await router.handle("yes", "telegram")
        _require(final and "Self-heal workflow completed" in final, "resume did not finish self-heal")
        _require(await _canary_count(db_path) >= 5, "approved self-heal did not seed canary proof")
        events = await latest_events(db_path, run_id, limit=40)
        names = " ".join(event["event"] for event in events)
        for required in ("diagnose", "snapshot", "plan_patch", "await_approval", "apply_patch_isolated", "verify", "final_report"):
            _require(required in names, f"missing checkpoint event {required}")


async def _decline_cancels() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-self-heal-decline-") as tmp:
        db_path = await _db(tmp)
        reply = await _complex_reply(db_path)
        run_id = _run_id(reply)
        router = HarnessRouter(db_path)
        await router.handle("yes", "telegram")
        declined = await router.handle("no", "telegram")
        _require(declined == "Okay, I won't do that.", "decline did not cancel cleanly")
        run = await get_run(db_path, run_id)
        _require(run["status"] == "cancelled", "declined run not cancelled")
        _require(await _canary_count(db_path) == 0, "decline still mutated canaries")


async def _verification_failure_report() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-self-heal-fail-") as tmp:
        db_path = await _db(tmp)
        await _complex_reply(db_path)
        router = HarnessRouter(db_path)
        await router.handle("yes", "telegram")
        async with aiosqlite.connect(db_path) as db:
            await db.execute("CREATE TABLE IF NOT EXISTS session_summaries (id INTEGER PRIMARY KEY, summary TEXT)")
            await db.execute("INSERT INTO session_summaries (summary) VALUES (?)", ("hotteok leaked back into memory",))
            await db.commit()
        failed = await router.handle("yes", "telegram")
        _require(failed and "failed verification" in failed.lower(), "verification failure was not reported")
        report = await latest_self_heal_report(db_path)
        _require(report and "verification failed" in str(report["issue"]).lower(), "repair report missing")


async def _complex_reply(db_path: str) -> str:
    old_env = {name: os.environ.get(name) for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY")}
    os.environ["OPENAI_API_KEY"] = os.environ["ANTHROPIC_API_KEY"] = os.environ["GOOGLE_API_KEY"] = "test"
    try:
        lanes = ModelLanes(db_path)
        lanes.mind = FakeMind()
        lanes.steward = FakeSteward()
        lanes.premium_sight = FakePremiumSight()
        return await lanes.complex_plan_response("self heal Maya after approval", "", "", "telegram")
    finally:
        for name, value in old_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


async def _db(tmp: str) -> str:
    db_path = str(Path(tmp) / "smoke.db")
    await init_db(db_path)
    await init_harness_db(db_path)
    return db_path


async def _canary_count(db_path: str) -> int:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM memory_canaries")
        row = await cursor.fetchone()
    return int(row[0])


def _run_id(text: str) -> str:
    match = re.search(r"execution workflow:\s*(hrn_[a-f0-9]+)", text)
    if not match:
        raise AssertionError("execution workflow id missing")
    return match.group(1)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
