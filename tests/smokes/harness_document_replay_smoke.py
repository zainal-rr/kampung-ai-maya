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

import maya_harness.harness_tools as harness_tools
from maya_harness.harness_artifact_store import latest_artifacts
from maya_harness.harness_models import local_artifact
from maya_harness.harness_state import initial_harness_state
from maya_harness.harness_store import init_harness_db
from maya_harness.harness_graph import HarnessGraphRunner
from maya_core.storage import init_db


CALLS = 0


async def main() -> None:
    global CALLS
    with tempfile.TemporaryDirectory(prefix="maya-doc-replay-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        await init_harness_db(db_path)
        original = harness_tools.HarnessTools._document
        harness_tools.HarnessTools._document = _fake_document
        try:
            state = initial_harness_state(
                run_id="doc_replay",
                thread_id="harness:doc_replay",
                channel="telegram",
                user_text="create an md file about replay",
                workflow_type="document",
            )
            state["user_turn_id"] = "doc_replay:turn"
            await HarnessGraphRunner(db_path).run(state)
            await HarnessGraphRunner(db_path).run(dict(state))
            artifacts = await latest_artifacts(db_path, "doc_replay", limit=10)
            _require(CALLS == 1, f"document side effect repeated {CALLS} times")
            _require(len(artifacts) == 1, f"duplicate artifacts: {len(artifacts)}")
            _require(artifacts[0]["checksum"], "artifact checksum missing")
        finally:
            harness_tools.HarnessTools._document = original
    print("harness_document_replay_smoke: ok")


async def _fake_document(self, text: str, channel: str) -> harness_tools.HarnessToolResult:
    global CALLS
    CALLS += 1
    path = Path(tempfile.gettempdir()) / "maya_doc_replay_once.md"
    path.write_text("# Replay\n", encoding="utf-8")
    artifact = local_artifact("note", str(path), "Replay note", "document")
    return harness_tools.HarnessToolResult(
        "completed",
        f"Created [file:{path}]",
        [str(path)],
        [artifact],
        next_step="document",
    )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
