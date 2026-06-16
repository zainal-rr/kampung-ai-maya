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

import maya_harness.harness_tools as harness_tools
from maya_harness.harness_router import HarnessRouter
from maya_harness.harness_state import initial_harness_state
from maya_harness.harness_store import init_harness_db, list_active_runs
from maya_core.storage import init_db


async def main() -> None:
    with tempfile.NamedTemporaryFile() as tmp:
        db_path = tmp.name
        await init_db(db_path)
        await init_harness_db(db_path)
        original = harness_tools.HarnessTools._general
        harness_tools.HarnessTools._general = _fake_general
        try:
            router = HarnessRouter(db_path)
            for idx in range(3):
                state = initial_harness_state(
                    run_id=f"run_{idx + 1}",
                    thread_id=f"harness:run_{idx + 1}",
                    channel="telegram",
                    user_text=f"workflow {idx + 1}",
                    workflow_type="general",
                )
                await router.runner.run(state)
            choices = await router.handle("continue", "telegram")
            _require(choices and "more than one" in choices.lower(), "multiple choice missing")
            selected = await router.handle("2", "telegram")
            _require(selected and "continued" in selected, "selected checkpoint did not resume")
            _require(selected.startswith("Continuing: general"), "selected checkpoint did not announce target")
            active = await list_active_runs(db_path)
            _require(len(active) == 3, "resume should not close other active workflows")
        finally:
            harness_tools.HarnessTools._general = original
    print("harness_multi_checkpoint_resume_smoke: ok")


async def _fake_general(self, text: str, channel: str) -> harness_tools.HarnessToolResult:
    return harness_tools.HarnessToolResult(
        "completed",
        f"continued {text}",
        next_step="general",
        keep_open=True,
    )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
