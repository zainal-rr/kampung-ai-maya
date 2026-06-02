from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from harness_store import get_run, latest_events, list_active_runs, record_event
from maya_harness_sdk import MayaHarnessSDK
from project_store import active_project


@dataclass(frozen=True)
class MayaThreadRef:
    thread_id: str
    kind: str
    channel: str
    run_id: str = ""
    workflow_type: str = ""
    status: str = ""
    goal: str = ""


class MayaThreadManager:
    """Thread identity and lookup wrapper for Maya surfaces and workflows."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.sdk = MayaHarnessSDK(db_path)

    async def start_thread(
        self,
        kind: str,
        *,
        scope: str = "",
        channel: str = "imac",
        goal: str = "",
        workflow_type: str | None = None,
        state: dict[str, Any] | None = None,
    ) -> MayaThreadRef:
        thread_id = await self.thread_id_for(kind, scope=scope, channel=channel)
        result = await self.sdk.start_thread(
            thread_id,
            channel=channel,
            workflow_type=workflow_type or kind,
            goal=goal,
            state=state,
        )
        return MayaThreadRef(thread_id, kind, channel, result.run_id, workflow_type or kind, result.status, goal)

    async def get_thread(self, run_id: str) -> MayaThreadRef | None:
        run = await get_run(self.db_path, run_id)
        return self._ref_from_run(run) if run else None

    async def active_threads(self, *, channel: str | None = None, limit: int = 20) -> list[MayaThreadRef]:
        runs = await list_active_runs(self.db_path, channel=channel, limit=limit)
        return [self._ref_from_run(run) for run in runs]

    async def touch_thread(self, run_id: str, event: str = "thread_touched", details: str = "") -> None:
        await record_event(self.db_path, run_id, event, details)

    async def resume_thread(
        self,
        thread_id: str,
        *,
        channel: str = "imac",
        run_id: str | None = None,
        approval_result: str | None = None,
    ) -> MayaThreadRef:
        result = await self.sdk.resume_thread(
            thread_id,
            channel=channel,
            run_id=run_id,
            approval_result=approval_result,
        )
        ref = await self.get_thread(result.run_id)
        return ref or MayaThreadRef(thread_id, _kind_from_thread_id(thread_id), channel, result.run_id, status=result.status)

    async def thread_events(self, run_id: str, limit: int = 8) -> list[dict[str, str]]:
        return await latest_events(self.db_path, run_id, limit=limit)

    async def thread_id_for(self, kind: str, *, scope: str = "", channel: str = "") -> str:
        normalized = _slug(kind)
        if normalized in {"telegram", "imac", "screen", "voice"}:
            return f"maya:{normalized}"
        if normalized in {"weekly-memory", "weekly-memory-background", "weekly"}:
            return "maya:background:weekly-memory"
        if normalized in {"project", "projects"}:
            return f"maya:project:{await self._project_scope(scope)}"
        if normalized in {"background", "task", "workflow"}:
            return f"maya:background:{_slug(scope) or 'general'}"
        if channel:
            return f"maya:{_slug(channel)}:{normalized}"
        return f"maya:{normalized}"

    async def _project_scope(self, scope: str) -> str:
        if scope:
            return _slug(scope)
        project = await active_project(self.db_path)
        if project:
            return _slug(project.name or Path(project.path).name)
        return "unassigned"

    def _ref_from_run(self, run: dict[str, Any]) -> MayaThreadRef:
        thread_id = str(run.get("thread_id") or "")
        return MayaThreadRef(
            thread_id=thread_id,
            kind=_kind_from_thread_id(thread_id),
            channel=str(run.get("channel") or ""),
            run_id=str(run.get("run_id") or ""),
            workflow_type=str(run.get("workflow_type") or ""),
            status=str(run.get("status") or ""),
            goal=str(run.get("goal") or ""),
        )


def _kind_from_thread_id(thread_id: str) -> str:
    parts = [part for part in thread_id.split(":") if part]
    if len(parts) >= 2 and parts[0] == "maya":
        return parts[1]
    return "general"


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "general"
