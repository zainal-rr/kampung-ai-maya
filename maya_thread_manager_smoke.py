from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from maya_thread_manager import MayaThreadManager


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-thread-manager-") as tmp:
        db_path = str(Path(tmp) / "threads.db")
        manager = MayaThreadManager(db_path)

        telegram = await manager.start_thread("telegram", channel="telegram", goal="Telegram chat")
        _require(telegram.thread_id == "maya:telegram", "telegram thread id wrong")
        _require(telegram.status == "running", "telegram thread not running")

        project = await manager.start_thread("project", scope="Kampung AI", channel="imac", goal="Project work")
        _require(project.thread_id == "maya:project:kampung-ai", "project thread id wrong")

        weekly_id = await manager.thread_id_for("weekly", channel="background")
        _require(weekly_id == "maya:background:weekly-memory", "weekly thread id wrong")

        active = await manager.active_threads(limit=5)
        ids = {thread.thread_id for thread in active}
        _require({"maya:telegram", "maya:project:kampung-ai"}.issubset(ids), "active threads missing")

        await manager.touch_thread(telegram.run_id, "thread_touched", "smoke")
        events = await manager.thread_events(telegram.run_id)
        _require(any(event["event"] == "thread_touched" for event in events), "touch event missing")

        resumed = await manager.resume_thread("maya:telegram", channel="telegram", run_id=telegram.run_id)
        _require(resumed.run_id == telegram.run_id, "resume returned wrong run")
    print("maya_thread_manager_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
