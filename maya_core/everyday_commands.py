from __future__ import annotations

from pathlib import Path

from maya_core.approval_inbox import approval_inbox_text
from maya_core.artisan_runner import latest_artisan_delivery_text
from daily_cockpit import daily_cockpit_text, focus_text, project_cockpit_text
from desktop_file_opener import DesktopFileOpener
from harness_artifact_store import latest_artifacts
from maya_desk import maya_desk_text
from storage import get_preference
from utils import OSBridge
from waiting_on import handle_waiting_on
from workflow_desk import background_tasks_text, close_matching_workflow, quiet_mode_text, workflow_desk_text
from everyday_document_summary import (
    _best_artifact_summary,
    _close_workflow_query,
    _content_summary,
    _pptx_content_summary,
    _summary_from_path,
)


def _latest_draft_request(cleaned: str) -> bool:
    words = set(cleaned.split())
    if not ({"draft", "rough"} & words):
        return False
    if cleaned.startswith(("draft ", "make ", "create ", "write ", "prepare ", "build ", "generate ")):
        return False
    retrieval_markers = (
        "give me",
        "send me",
        "show me",
        "open",
        "where is",
        "do you have",
        "if any",
        "any draft",
        "any rough",
        "the draft",
        "the rough",
        "rough draft",
    )
    return any(marker in cleaned for marker in retrieval_markers)


class EverydayCommandRouter:
    def __init__(self, db_path: str, bridge: OSBridge | None = None):
        self.db_path = db_path
        self.bridge = bridge or OSBridge()
        self.file_opener = DesktopFileOpener(self.bridge)
        self.last_lane = ""
        self.last_reason = ""

    async def handle(self, text: str, channel: str) -> str | None:
        self.last_lane = ""
        self.last_reason = ""
        quiet = await quiet_mode_text(self.db_path, text)
        if quiet:
            self._mark("quiet mode")
            return quiet
        waiting = await handle_waiting_on(self.db_path, text, channel)
        if waiting:
            self._mark("waiting-on tracker")
            return waiting
        cleaned = " ".join(text.lower().split()).rstrip("?.! ")
        if cleaned in {"what does today look like", "good morning maya", "hello maya today"}:
            self._mark("daily cockpit")
            return await daily_cockpit_text(self.db_path, channel)
        if cleaned in {
            "what should i focus on",
            "what should i focus on today",
            "what should i focus on first",
            "what should i focus on this morning",
            "what should i focus on tonight",
        }:
            self._mark("daily focus")
            return await focus_text(self.db_path)
        if cleaned in {"what needs my approval", "show approvals", "show approval inbox", "approval inbox", "anything waiting for me"}:
            self._mark("approval inbox")
            return await approval_inbox_text(self.db_path)
        if cleaned in {"what are you doing", "show workflow desk", "workflow desk"}:
            self._mark("workflow desk")
            return await workflow_desk_text(self.db_path)
        if cleaned in {"show background tasks", "background tasks"}:
            self._mark("workflow desk")
            return await background_tasks_text(self.db_path)
        if cleaned in {"show project cockpit", "project cockpit", "what is next for this project"}:
            self._mark("project cockpit")
            return await project_cockpit_text(self.db_path)
        if cleaned in {"show maya desk", "refresh maya desk", "open maya desk", "what changed today"}:
            self._mark("maya desk")
            return await self._maya_desk(channel)
        close_query = _close_workflow_query(text)
        if close_query:
            self._mark("workflow desk")
            return await close_matching_workflow(self.db_path, close_query)
        if cleaned in {
            "what was the last document you created",
            "what is the last document you created",
            "what was the latest document you created",
            "what is the latest document you created",
            "what document did you just create",
            "what document did you create just now",
            "what file did you just create",
            "what file did you create just now",
            "what did you just create",
            "what did you create just now",
            "what document did you create",
            "what file did you create",
            "what was the last document",
            "what is the last document",
            "last document",
            "latest document",
        }:
            self._mark("latest document")
            return await self._latest_document(channel)
        if cleaned in {
            "open latest document",
            "open the last document",
            "send latest document",
            "send the latest document",
            "send me latest document",
            "send me the latest document",
            "send last document",
            "send the last document",
            "send me last document",
            "send me the last document",
        }:
            self._mark("latest document")
            return await self._open_latest_document(channel)
        if cleaned in {
            "give me the rough",
            "send me the rough",
            "show me the rough",
            "give me the draft",
            "send me the draft",
            "show me the draft",
            "send draft",
            "send the draft",
            "send rough draft",
            "send the rough draft",
            "show rough draft",
            "show the rough draft",
        } or _latest_draft_request(cleaned):
            self._mark("draft document")
            return await self._open_latest_draft(channel)
        if cleaned in {
            "open latest file",
            "open the last file",
            "open latest artifact",
            "send latest file",
            "send the latest file",
            "send me latest file",
            "send me the latest file",
            "send latest artifact",
            "send me latest artifact",
        }:
            self._mark("artifact action")
            return await self._open_latest_file(channel)
        if cleaned in {
            "last app",
            "latest app",
            "send last app",
            "send the last app",
            "send me the last app",
            "send latest app",
            "send me latest app",
            "where is the last app",
            "where is my last app",
        }:
            self._mark("latest app")
            return await latest_artisan_delivery_text(self.db_path, "app", channel)
        if cleaned in {
            "last 3d model",
            "latest 3d model",
            "last 3d print",
            "latest 3d print",
            "send last 3d model",
            "send the last 3d model",
            "send me the last 3d model",
            "send last 3d print",
            "send me the last 3d print",
            "where is the last 3d model",
            "where is my last 3d model",
        }:
            self._mark("latest maker")
            return await latest_artisan_delivery_text(self.db_path, "maker", channel)
        file_reply = await self.file_opener.handle(text, channel)
        if file_reply:
            self._mark("desktop file open")
            return file_reply
        return None

    def _mark(self, reason: str) -> None:
        self.last_lane = "command"
        self.last_reason = reason

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

    async def _latest_document(self, channel: str) -> str:
        path = await get_preference(self.db_path, "maya_last_document_path")
        if not path:
            return "I do not have a last document path saved yet."
        exists = "yes" if Path(path).exists() else "no"
        summary = await self._document_summary(path)
        return f"Last document:\n1) path: {path}\n2) exists on iMac: {exists}\n3) summary: {summary}"

    async def _open_latest_document(self, channel: str) -> str:
        path = await get_preference(self.db_path, "maya_last_document_path")
        if not path:
            return "I do not have a last document path saved yet."
        summary = await self._document_summary(path)
        if channel == "telegram":
            return f"Last document: {path}\nSummary: {summary}\n[file:{path}]"
        try:
            self.bridge.open_file(path, None)
        except Exception as exc:
            return f"I found the last document at {path}, but I could not open it: {exc}"
        return f"I opened the last document: {path}"

    async def _open_latest_draft(self, channel: str) -> str:
        path = await get_preference(self.db_path, "maya_last_draft_document_path")
        if not path:
            return "I do not have a rejected draft saved right now."
        document_path = Path(path)
        if not document_path.exists():
            return f"I had a draft path saved, but I cannot find it now: {path}"
        summary = await self._document_summary(path)
        if channel == "telegram":
            return f"Draft document: {path}\nSummary: {summary}\n[file:{path}]"
        try:
            self.bridge.open_file(path, None)
        except Exception as exc:
            return f"I found the draft at {path}, but I could not open it: {exc}"
        return f"I opened the draft: {path}"

    async def _document_summary(self, path: str) -> str:
        document_path = Path(path)
        local_summary = _content_summary(document_path)
        if local_summary:
            return local_summary
        pptx_summary = _pptx_content_summary(document_path)
        if pptx_summary:
            return pptx_summary
        artifacts = await latest_artifacts(self.db_path, limit=30)
        summaries = [
            artifact
            for artifact in artifacts
            if str(artifact.get("path") or "") == path
            and str(artifact.get("summary") or "").strip()
        ]
        artifact_summary = _best_artifact_summary(summaries)
        if artifact_summary:
            return artifact_summary
        return _summary_from_path(document_path)
