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

from maya_harness.harness_store import latest_events
from maya_core.maya_event_store import MayaEventStore
from maya_core.maya_thread_manager import MayaThreadManager


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-event-store-") as tmp:
        db_path = str(Path(tmp) / "events.db")
        manager = MayaThreadManager(db_path)
        thread = await manager.start_thread("telegram", channel="telegram", goal="event smoke")
        store = MayaEventStore(db_path)

        first = await store.append(
            "user_message",
            thread_id=thread.thread_id,
            run_id=thread.run_id,
            actor="zainal",
            summary="hello",
            payload={"channel": "telegram"},
        )
        second = await store.append(
            "artifact_created",
            thread_id=thread.thread_id,
            run_id=thread.run_id,
            summary="demo artifact",
            payload={"kind": "docx"},
        )
        _require(second > first, "events are not append-only ordered")

        rows = await store.list(thread_id=thread.thread_id)
        _require([row["event_type"] for row in rows][-2:] == ["user_message", "artifact_created"], "thread events wrong")
        _require(rows[-1]["payload"]["kind"] == "docx", "payload was not decoded")

        mirrored = await latest_events(db_path, thread.run_id, limit=5)
        names = [event["event"] for event in mirrored]
        _require("user_message" in names and "artifact_created" in names, "harness mirror missing")
    print("maya_event_store_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
