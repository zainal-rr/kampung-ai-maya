from __future__ import annotations

import re

from approval_inbox import approval_inbox_text
from daily_cockpit import daily_cockpit_text, focus_text, project_cockpit_text
from harness_artifact_store import latest_artifacts
from maya_desk import maya_desk_text
from utils import OSBridge
from waiting_on import handle_waiting_on
from workflow_desk import background_tasks_text, close_matching_workflow, quiet_mode_text, workflow_desk_text


class EverydayCommandRouter:
    def __init__(self, db_path: str, bridge: OSBridge | None = None):
        self.db_path = db_path
        self.bridge = bridge or OSBridge()

    async def handle(self, text: str, channel: str) -> str | None:
        quiet = await quiet_mode_text(self.db_path, text)
        if quiet:
            return quiet
        waiting = await handle_waiting_on(self.db_path, text, channel)
        if waiting:
            return waiting
        cleaned = " ".join(text.lower().split())
        if cleaned in {"what does today look like", "good morning maya", "hello maya today"}:
            return await daily_cockpit_text(self.db_path, channel)
        if cleaned in {"what should i focus on", "what should i focus on first"}:
            return await focus_text(self.db_path)
        if cleaned in {"what needs my approval", "show approvals", "show approval inbox", "approval inbox", "anything waiting for me"}:
            return await approval_inbox_text(self.db_path)
        if cleaned in {"what are you doing", "show workflow desk", "workflow desk"}:
            return await workflow_desk_text(self.db_path)
        if cleaned in {"show background tasks", "background tasks"}:
            return await background_tasks_text(self.db_path)
        if cleaned in {"show project cockpit", "project cockpit", "what is next for this project"}:
            return await project_cockpit_text(self.db_path)
        if cleaned in {"show maya desk", "refresh maya desk", "open maya desk", "what changed today"}:
            return await self._maya_desk(channel)
        close_query = _close_workflow_query(text)
        if close_query:
            return await close_matching_workflow(self.db_path, close_query)
        if cleaned in {"open latest file", "open the last file", "open latest artifact"}:
            return await self._open_latest_file(channel)
        return None

    async def _maya_desk(self, channel: str) -> str:
        reply = await maya_desk_text(self.db_path)
        if channel == "telegram":
            return reply
        path = reply.splitlines()[0].split(": ", 1)[-1]
        try:
            self.bridge.open_file(path, None)
        except Exception:
            pass
        return f"I refreshed Maya desk: {path}"

    async def _open_latest_file(self, channel: str) -> str:
        artifacts = await latest_artifacts(self.db_path, limit=1)
        if not artifacts or not artifacts[0].get("path"):
            return "I do not have a recent file artifact to open yet."
        path = str(artifacts[0]["path"])
        if channel == "telegram":
            return f"Latest file: {path}\n[file:{path}]"
        try:
            self.bridge.open_file(path, None)
        except Exception as exc:
            return f"I found the latest file at {path}, but I could not open it: {exc}"
        return f"I opened the latest file: {path}"


def _close_workflow_query(text: str) -> str | None:
    match = re.match(r"^(?:pause|close|cancel)\s+(?:the\s+)?(.+?)\s+(?:task|workflow)$", text, re.I)
    return match.group(1).strip(" .") if match else None
