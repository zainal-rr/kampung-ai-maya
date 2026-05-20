from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from route_tracker import last_route_text, record_route
from storage import init_db


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-route-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        empty = await last_route_text(db_path)
        _require(empty == "No route recorded yet.", "empty route text was wrong")
        await record_route(db_path, "voice note", "Kimi coding", "coding question", True)
        text = await last_route_text(db_path)
        _require("voice note" in text, "input type missing")
        _require("Kimi coding" in text, "lane missing")
        _require("cost recorded: yes" in text, "cost flag missing")
        print("route_tracker_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
