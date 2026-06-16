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

from harness_resume import build_resume_summary
from harness_state import initial_harness_state
from harness_store import init_harness_db, upsert_run
from storage import init_db


async def main() -> None:
    with tempfile.NamedTemporaryFile() as tmp:
        db_path = tmp.name
        await init_db(db_path)
        await init_harness_db(db_path)
        state = initial_harness_state(
            run_id="resume_1",
            thread_id="maya:browser",
            channel="telegram",
            user_text="check flight to Penang",
            workflow_type="browser",
        )
        state["last_successful_step"] = "inspect browser"
        state["next_suggested_step"] = "compare results"
        await upsert_run(db_path, state, status="running")
        text = await build_resume_summary(db_path, "telegram")
        _require("Workflow: browser" in text, "workflow missing")
        _require("compare results" in text, "next step missing")
    print("harness_resume_detail_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
