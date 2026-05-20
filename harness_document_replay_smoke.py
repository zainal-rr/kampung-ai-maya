from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import harness_tools
from harness_artifact_store import latest_artifacts
from harness_models import local_artifact
from harness_state import initial_harness_state
from harness_store import init_harness_db
from harness_graph import HarnessGraphRunner
from storage import init_db


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
