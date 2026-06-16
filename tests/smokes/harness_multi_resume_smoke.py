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

from maya_harness.harness_router import HarnessRouter
from maya_harness.harness_state import initial_harness_state
from maya_harness.harness_store import init_harness_db, upsert_run
from maya_core.storage import init_db


async def main() -> None:
    with tempfile.NamedTemporaryFile() as tmp:
        db_path = tmp.name
        await init_db(db_path)
        await init_harness_db(db_path)
        for idx, workflow in enumerate(("browser", "screen"), start=1):
            state = initial_harness_state(
                run_id=f"run_{idx}",
                thread_id=f"maya:{workflow}",
                channel="telegram",
                user_text=f"{workflow} work",
                workflow_type=workflow,
            )
            state["keep_open"] = True
            await upsert_run(db_path, state, status="running")
        router = HarnessRouter(db_path)
        choices = await router.handle("continue", "telegram")
        _require(choices and "more than one" in choices.lower(), "multiple workflow choice missing")
        selected = await router.handle("2", "telegram")
        _require(selected and selected.startswith("Continuing: screen"), "numeric workflow did not announce target")
    print("harness_multi_resume_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
