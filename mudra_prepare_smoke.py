from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from hardware_event_store import init_hardware_event_db, latest_hardware_events
from mudra_adapter import MudraAdapter


class FakeAssistant:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.called = False

    async def handle_text(self, *args, **kwargs):
        self.called = True


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir, tempfile.NamedTemporaryFile() as tmp_db:
        event_dir = Path(tmp_dir)
        db_path = tmp_db.name
        await init_hardware_event_db(db_path)
        (event_dir / "event.json").write_text(
            json.dumps({"gesture": "double_pinch", "wearing": True, "distance_m": 0.5}),
            encoding="utf-8",
        )
        fake = FakeAssistant(db_path)
        await MudraAdapter(fake, str(event_dir))._process(event_dir / "event.json")
        events = await latest_hardware_events(db_path, "mudra")
        _require(events and events[0]["status"] == "prepared_only", "mudra event not logged")
        _require(not fake.called, "mudra gesture triggered an action")
    print("mudra_prepare_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
