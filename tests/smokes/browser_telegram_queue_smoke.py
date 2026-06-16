from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from browser_workflows import HumanBrowserWorkflowRouter
from storage import get_preference, init_db


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "maya.db")
        await init_db(db_path)
        router = HumanBrowserWorkflowRouter(db_path)
        reply = await router.handle("find flights to Penang next Friday", "telegram")
        _require(reply is not None and "queued the flight search" in reply.lower(), "Telegram browser start should be queued")
        _require("stop before booking or payment" in reply.lower(), "flight safety boundary missing")
        state = await get_preference(db_path, "maya_browser_workflow")
        _require(state is not None and "queued browser search" in state, "queued browser state was not saved")
    print("browser_telegram_queue_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
