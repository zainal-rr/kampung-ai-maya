from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import aiosqlite

from canonical_memory import search_canonical_direct_fact
from harness_artifact_store import latest_artifacts
from harness_store import get_run, latest_events
from maya_harness_sdk import MayaHarnessSDK


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

        tool = await sdk.call_tool(
            "maya:telegram",
            "file.create",
            action_type="create_file",
            args={"path": str(artifact_path)},
            channel="telegram",
        )
        _require(tool.status == "completed", "allowed tool did not complete")

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
        _require(await _approval_count(db_path, start.run_id) == 1, "approval row missing")

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
