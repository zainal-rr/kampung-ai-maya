from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from maya_harness.harness_router import HarnessRouter
from maya_harness.harness_state import initial_harness_state
from maya_harness.harness_store import init_harness_db, upsert_run
from maya_core.storage import init_db


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-workflow-doc-bypass-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        await init_harness_db(db_path)
        router = HarnessRouter(db_path)
        for idx, goal in enumerate(
            (
                "Execute approved /complex plan: plan a self heal for Maya memory but do not change files",
                "open Airbnb and reserve the apartment without confirmation",
            ),
            start=1,
        ):
            state = initial_harness_state(
                run_id=f"run_{idx}",
                thread_id=f"harness:run_{idx}",
                channel="telegram",
                user_text=goal,
                workflow_type="self_heal" if idx == 1 else "app",
            )
            await upsert_run(db_path, state, status="running")

        request = "can you put the last five question in a doc file? create the file and save it in folder"
        reply = await router.handle(request, "telegram")
        _require(reply is None, f"document request was hijacked by workflow resume: {reply}")

        choices = await router.handle("continue", "telegram")
        _require(choices and "more than one workflow open" in choices, "normal multi-workflow continue broke")

    print("workflow_document_bypass_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
