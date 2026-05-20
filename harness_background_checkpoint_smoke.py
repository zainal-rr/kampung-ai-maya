from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import harness_tools
from harness_graph import HarnessGraphRunner
from harness_store import init_harness_db
from storage import init_db


DELIVERIES = 0


async def main() -> None:
    global DELIVERIES
    with tempfile.TemporaryDirectory(prefix="maya-bg-replay-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        await init_harness_db(db_path)
        original = harness_tools.HarnessTools._scheduled
        harness_tools.HarnessTools._scheduled = _fake_scheduled
        task = {"id": 7, "action_type": "scheduled_briefing", "channel": "telegram", "title": "Morning brief"}
        try:
            await HarnessGraphRunner(db_path).run_background_task(task)
            await HarnessGraphRunner(db_path).run_background_task(task)
            _require(DELIVERIES == 1, f"scheduled delivery repeated {DELIVERIES} times")
        finally:
            harness_tools.HarnessTools._scheduled = original
    print("harness_background_checkpoint_smoke: ok")


async def _fake_scheduled(self, text: str, channel: str) -> harness_tools.HarnessToolResult:
    global DELIVERIES
    DELIVERIES += 1
    return harness_tools.HarnessToolResult("completed", f"Delivered {text}", next_step="scheduled")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
