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

import aiosqlite

from maya_memory.canonical_memory import search_canonical_direct_fact
from maya_harness.harness_artifact_store import latest_artifacts
from maya_harness.harness_store import get_run, latest_events
from maya_core.maya_harness_sdk import MayaHarnessSDK


async def _message_handler(message: str, channel: str, thread_id: str, run_id: str) -> str:
    return f"handled {channel} {thread_id} {run_id}: {message}"


async def _tool_executor(tool_name: str, args: dict) -> dict:
    return {"tool": tool_name, "args": args, "ok": True}


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-sdk-") as tmp:
        db_path = str(Path(tmp) / "sdk.db")
        artifact_path = Path(tmp) / "demo.txt"
        artifact_path.write_text("demo", encoding="utf-8")
        sdk = MayaHarnessSDK(db_path, message_handler=_message_handler, tool_executor=_tool_executor)

        start = await sdk.start_thread(
            "maya:telegram",
            channel="telegram",
            workflow_type="conversation",
            goal="SDK smoke",
        )
        _require(start.status == "running", "thread did not start")

        message = await sdk.send_message("maya:telegram", "hello", channel="telegram")
        _require(message.message.startswith("handled telegram maya:telegram"), "message handler not called")

        trusted_artifact_path = workspace_artifact_path(tmp)
        tool = await sdk.call_tool(
            "maya:telegram",
            "file.create",
            action_type="create_file",
            args={"path": str(trusted_artifact_path)},
            field_provenance={"path": "maya_derived"},
            channel="telegram",
        )
        _require(tool.status == "completed", "allowed tool did not complete")

        forged = await sdk.call_tool(
            "maya:telegram",
            "file.create",
            action_type="create_file",
            args={"path": str(trusted_artifact_path), "path_source": "maya_derived"},
            field_provenance={"path": "email"},
            channel="telegram",
        )
        _require(forged.status == "requires_approval", "forged planner source label did not require approval")
        _require("path must be Maya-derived" in forged.data["permission_reason"], "forged approval reason lost predicate reason")
        await sdk.resume_thread("maya:telegram", channel="telegram", approval_result="approved")

        approval = await sdk.call_tool(
            "maya:telegram",
            "file.delete",
            action_type="delete_file",
            args={"path": str(artifact_path)},
            channel="telegram",
        )
        _require(approval.status == "requires_approval", "dangerous tool did not require approval")
        paused = await get_run(db_path, start.run_id)
        _require(paused and paused["status"] == "paused", "approval did not pause run")
        _require(await _approval_count(db_path, start.run_id) == 2, "approval rows missing")

        await sdk.resume_thread("maya:telegram", channel="telegram", approval_result="approved")
        resumed = await get_run(db_path, start.run_id)
        _require(resumed and resumed["status"] == "running", "resume did not reopen run")

        artifact = await sdk.create_artifact(
            "maya:telegram",
            kind="note",
            path=str(artifact_path),
            summary="SDK artifact",
            channel="telegram",
        )
        _require(artifact.data["exists_status"] == "exists", "artifact existence not recorded")
        rows = await latest_artifacts(db_path, start.run_id)
        _require(rows and rows[0]["kind"] == "note", "artifact row missing")

        memory = await sdk.write_memory(
            "maya:telegram",
            content="my sdk test drink is milo",
            kind="preference",
            channel="telegram",
        )
        _require(memory.data["memory_id"], "memory id missing")
        recalled = await search_canonical_direct_fact(db_path, "what is my sdk test drink?")
        _require(recalled and "milo" in recalled[0], "canonical memory was not recallable")

        events = await latest_events(db_path, start.run_id, limit=20)
        event_names = [event["event"] for event in events]
        for expected in (
            "thread_started",
            "user_message",
            "tool_requested",
            "approval_requested",
            "workflow_resumed",
            "artifact_created",
            "memory_written",
        ):
            _require(expected in event_names, f"{expected} event missing")
    print("maya_harness_sdk_smoke: ok")


def workspace_artifact_path(seed: str) -> Path:
    from maya_core.workspace_paths import workspace_dir

    suffix = Path(seed).name.replace("/", "_")
    return workspace_dir("artifacts") / f"sdk-{suffix}.txt"


async def _approval_count(db_path: str, run_id: str) -> int:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM harness_approvals WHERE run_id = ?", (run_id,))
        row = await cursor.fetchone()
    return int(row[0] if row else 0)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
