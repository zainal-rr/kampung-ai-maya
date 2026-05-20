from __future__ import annotations

import asyncio
import tempfile

from harness_graph import HarnessGraphRunner
from harness_state import initial_harness_state
from harness_store import get_active_run, init_harness_db
from storage import init_db


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def main() -> None:
    with tempfile.NamedTemporaryFile() as tmp:
        db_path = tmp.name
        await init_db(db_path)
        await init_harness_db(db_path)
        state = initial_harness_state(
            run_id="smoke_graph",
            thread_id="maya:shared",
            channel="telegram",
            user_text="remember to check router",
            workflow_type="scheduled",
        )
        result = await HarnessGraphRunner(db_path).run(state)
        _require("final_response" in result, "graph did not produce final response")
        active = await get_active_run(db_path, "telegram")
        _require(active is None, "completed graph stayed active")
    print("harness_graph_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
