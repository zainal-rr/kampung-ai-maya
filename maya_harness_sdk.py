from __future__ import annotations

import inspect
import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import aiosqlite

from canonical_memory import upsert_canonical_memory
from harness_artifact_store import record_structured_artifact
from harness_models import local_artifact
from harness_store import (
    create_approval,
    get_run,
    init_harness_db,
    new_run_id,
    record_event,
    resolve_approval,
    upsert_run,
)
from maya_permission_kernel import MayaPermissionKernel

MessageHandler = Callable[[str, str, str, str], str | Awaitable[str]]
ToolExecutor = Callable[[str, Mapping[str, Any]], Any | Awaitable[Any]]


@dataclass(frozen=True)
class MayaSDKResult:
    status: str
    run_id: str
    thread_id: str
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)


class MayaHarnessSDK:
    """Minimal SDK facade over existing harness, approval, memory, and artifact stores."""

    def __init__(
        self,
        db_path: str,
        *,
        message_handler: MessageHandler | None = None,
        tool_executor: ToolExecutor | None = None,
    ):
        self.db_path = db_path
        self.message_handler = message_handler
        self.tool_executor = tool_executor
        self.permission_kernel = MayaPermissionKernel()

    async def start_thread(
        self,
        thread_id: str,
        *,
        channel: str = "imac",
        workflow_type: str = "conversation",
        goal: str = "",
        state: Mapping[str, Any] | None = None,
        run_id: str | None = None,
    ) -> MayaSDKResult:
        actual_run_id = run_id or new_run_id()
        run_state = {
            "run_id": actual_run_id,
            "thread_id": thread_id,
            "channel": channel,
            "workflow_type": workflow_type,
            "goal": goal,
            "sdk_boundary": "maya_harness_sdk",
            **dict(state or {}),
        }
        await upsert_run(self.db_path, run_state, status="running")
        await record_event(self.db_path, actual_run_id, "thread_started", goal)
        return MayaSDKResult("running", actual_run_id, thread_id, data=run_state)

    async def send_message(
        self,
        thread_id: str,
        message: str,
        *,
        channel: str = "imac",
        run_id: str | None = None,
    ) -> MayaSDKResult:
        run = await self._ensure_run(thread_id, channel=channel, run_id=run_id)
        actual_run_id = str(run["run_id"])
        await record_event(self.db_path, actual_run_id, "user_message", message)
        response = ""
        if self.message_handler:
            handled = self.message_handler(message, channel, thread_id, actual_run_id)
            response = await handled if inspect.isawaitable(handled) else str(handled)
            await record_event(self.db_path, actual_run_id, "assistant_message", response)
        return MayaSDKResult("message_recorded", actual_run_id, thread_id, response)

    async def call_tool(
        self,
        thread_id: str,
        tool_name: str,
        *,
        action_type: str = "follow_up",
        args: Mapping[str, Any] | None = None,
        channel: str = "imac",
        run_id: str | None = None,
    ) -> MayaSDKResult:
        run = await self._ensure_run(thread_id, channel=channel, run_id=run_id)
        actual_run_id = str(run["run_id"])
        payload = dict(args or {})
        permission = self.permission_kernel.check(tool_name, action_type=action_type, args=payload)
        details = f"{tool_name} {json.dumps(payload, sort_keys=True, default=str)}"
        if permission.decision == "deny":
            await record_event(self.db_path, actual_run_id, "tool_denied", permission.reason)
            return MayaSDKResult("denied", actual_run_id, thread_id, permission.reason)
        if permission.decision == "confirm":
            approval = await self.request_approval(
                thread_id,
                action=permission.action_type,
                details=details,
                channel=channel,
                run_id=actual_run_id,
            )
            return MayaSDKResult(
                "requires_approval",
                actual_run_id,
                thread_id,
                "Approval required before tool execution.",
                {"approval": approval.data},
            )
        await record_event(self.db_path, actual_run_id, "tool_requested", details)
        if not self.tool_executor:
            await record_event(self.db_path, actual_run_id, "tool_completed", "recorded without executor")
            return MayaSDKResult("recorded", actual_run_id, thread_id, "Tool request recorded.")
        result = self.tool_executor(tool_name, payload)
        output = await result if inspect.isawaitable(result) else result
        await record_event(self.db_path, actual_run_id, "tool_completed", str(output)[:1000])
        return MayaSDKResult("completed", actual_run_id, thread_id, data={"output": output})

    async def request_approval(
        self,
        thread_id: str,
        *,
        action: str,
        details: str,
        channel: str = "imac",
        run_id: str | None = None,
    ) -> MayaSDKResult:
        run = await self._ensure_run(thread_id, channel=channel, run_id=run_id)
        actual_run_id = str(run["run_id"])
        state = dict(run.get("state") or {})
        state.update(
            {
                "run_id": actual_run_id,
                "thread_id": thread_id,
                "channel": channel,
                "pending_approval": {"action": action, "details": details[:1000]},
            }
        )
        await create_approval(self.db_path, actual_run_id, action, details)
        await upsert_run(self.db_path, state, status="paused")
        await record_event(self.db_path, actual_run_id, "approval_requested", f"{action}: {details}")
        return MayaSDKResult("paused", actual_run_id, thread_id, data=state["pending_approval"])

    async def create_artifact(
        self,
        thread_id: str,
        *,
        kind: str,
        path: str,
        summary: str = "",
        source_tool: str = "maya_harness_sdk",
        channel: str = "imac",
        run_id: str | None = None,
    ) -> MayaSDKResult:
        run = await self._ensure_run(thread_id, channel=channel, run_id=run_id)
        actual_run_id = str(run["run_id"])
        artifact = local_artifact(kind, path, summary, source_tool)
        await record_structured_artifact(self.db_path, actual_run_id, artifact)
        await record_event(self.db_path, actual_run_id, "artifact_created", f"{kind}: {path}")
        return MayaSDKResult("artifact_recorded", actual_run_id, thread_id, data=artifact.as_dict())

    async def write_memory(
        self,
        thread_id: str,
        *,
        content: str,
        kind: str = "lesson",
        scope: str = "global",
        channel: str = "imac",
        confidence: str = "high",
        run_id: str | None = None,
    ) -> MayaSDKResult:
        run = await self._ensure_run(thread_id, channel=channel, run_id=run_id)
        actual_run_id = str(run["run_id"])
        memory_id = await upsert_canonical_memory(
            self.db_path,
            raw_text=content,
            content=content,
            kind=kind,
            scope=scope,
            source_channel=channel,
            source_ref=actual_run_id,
            confidence=confidence,
        )
        await record_event(self.db_path, actual_run_id, "memory_written", memory_id)
        return MayaSDKResult("memory_written", actual_run_id, thread_id, data={"memory_id": memory_id})

    async def resume_thread(
        self,
        thread_id: str,
        *,
        channel: str = "imac",
        run_id: str | None = None,
        approval_result: str | None = None,
    ) -> MayaSDKResult:
        run = await self._ensure_run(thread_id, channel=channel, run_id=run_id)
        actual_run_id = str(run["run_id"])
        state = dict(run.get("state") or {})
        status = "running"
        if approval_result:
            await resolve_approval(self.db_path, actual_run_id, approval_result)
            state["approval_result"] = approval_result
            state["pending_approval"] = {}
            if approval_result not in {"approved", "approve"}:
                status = "cancelled"
        await upsert_run(self.db_path, {**state, "run_id": actual_run_id, "thread_id": thread_id, "channel": channel}, status=status)
        await record_event(self.db_path, actual_run_id, "workflow_resumed", approval_result or "")
        return MayaSDKResult(status, actual_run_id, thread_id, data=state)

    async def _ensure_run(self, thread_id: str, *, channel: str, run_id: str | None = None) -> dict[str, Any]:
        if run_id:
            run = await get_run(self.db_path, run_id)
            if run:
                return run
        run = await _latest_thread_run(self.db_path, thread_id)
        if run:
            return run
        started = await self.start_thread(thread_id, channel=channel)
        return await get_run(self.db_path, started.run_id) or started.data


async def _latest_thread_run(db_path: str, thread_id: str) -> dict[str, Any] | None:
    await init_harness_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT run_id FROM harness_runs WHERE thread_id = ? "
            "AND status IN ('running', 'paused') ORDER BY updated_at DESC LIMIT 1",
            (thread_id,),
        )
        row = await cursor.fetchone()
    return await get_run(db_path, row[0]) if row else None
