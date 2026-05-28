from __future__ import annotations

import re
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree

from approval_inbox import approval_inbox_text
from daily_cockpit import daily_cockpit_text, focus_text, project_cockpit_text
from desktop_file_opener import DesktopFileOpener
from harness_artifact_store import latest_artifacts
from maya_desk import maya_desk_text
from storage import get_preference
from utils import OSBridge
from waiting_on import handle_waiting_on
from workflow_desk import background_tasks_text, close_matching_workflow, quiet_mode_text, workflow_desk_text


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
        if cleaned in {"open latest document", "open the last document"}:
            self._mark("latest document")
            return await self._open_latest_document(channel)
        if cleaned in {"open latest file", "open the last file", "open latest artifact"}:
            self._mark("artifact action")
            return await self._open_latest_file(channel)
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

    async def _document_summary(self, path: str) -> str:
        local_summary = _content_summary(Path(path))
        if local_summary:
            return local_summary
        artifacts = await latest_artifacts(self.db_path, limit=20)
        for artifact in artifacts:
            if str(artifact.get("path") or "") == path:
                summary = str(artifact.get("summary") or "").strip()
                if summary:
                    return summary
        return _summary_from_path(Path(path))


def _close_workflow_query(text: str) -> str | None:
    match = re.match(r"^(?:pause|close|cancel)\s+(?:the\s+)?(.+?)\s+(?:task|workflow)$", text, re.I)
    return match.group(1).strip(" .") if match else None


def _summary_from_path(path: Path) -> str:
    stem = path.stem.replace("-", " ").replace("_", " ").strip()
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return f"Word document about {stem}."
    if suffix == ".pptx":
        return f"PowerPoint presentation about {stem}."
    if suffix == ".xlsx":
        return f"Excel spreadsheet for {stem}."
    if suffix == ".html":
        return f"HTML file for {stem}."
    return f"File about {stem}."


def _content_summary(path: Path) -> str:
    if not path.exists() or path.suffix.lower() != ".docx":
        return ""
    paragraphs = _docx_paragraphs(path)
    if not paragraphs:
        return ""
    title = paragraphs[0]
    headings = _interesting_headings(paragraphs[1:])
    detail = _first_detail(paragraphs[1:])
    subject = _summary_subject(title)
    sentence = subject
    if headings:
        sentence += " covering " + _friendly_topics(headings[:4])
    if detail:
        sentence += ". " + _friendly_detail(detail)
    return sentence.rstrip(".") + "."


def _docx_paragraphs(path: Path) -> list[str]:
    try:
        with ZipFile(path) as archive:
            xml = archive.read("word/document.xml")
    except (KeyError, OSError):
        return []
    root = ElementTree.fromstring(xml)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", namespace)).strip()
        if text:
            paragraphs.append(text)
    return paragraphs


def _interesting_headings(paragraphs: list[str]) -> list[str]:
    generic = {"role and assumptions", "working context", "key decisions", "plan", "next steps"}
    headings = []
    for text in paragraphs:
        lowered = text.lower().strip()
        if lowered in generic:
            headings.append(text)
        elif re.match(r"^(?:day\s+\d+|budget|timeline|itinerary)\b", lowered):
            headings.append(text)
        if len(headings) >= 5:
            break
    return headings


def _first_detail(paragraphs: list[str]) -> str:
    for text in paragraphs:
        lowered = text.lower()
        if lowered.startswith(("role:", "assumption")):
            continue
        if any(marker in lowered for marker in ("kyoto", "tokyo", "trip", "itinerary", "arrival", "departure")):
            return text[:180].rstrip(".")
    return ""


def _join_phrases(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + ", and " + items[-1]


def _summary_subject(title: str) -> str:
    lowered = title.lower()
    day_match = re.match(r"^(?P<count>one|two|three|four|five|six|seven|\d+)\s+days?\s+(?P<place>.+?)\s+trip$", title, re.I)
    if day_match:
        count = day_match.group("count").lower()
        place = day_match.group("place").strip()
        return f"A {count}-day {place} trip plan"
    if "trip" in lowered or "itinerary" in lowered:
        return f"A {title} plan"
    return f"A {title}"


def _friendly_topics(headings: list[str]) -> str:
    cleaned = []
    for heading in headings:
        mapped = _topic_label(heading)
        if mapped:
            cleaned.append(mapped)
            continue
        text = re.sub(r"^Day\s+(\d+):\s*", r"Day \1 ", heading, flags=re.I)
        text = text.replace("&", "and")
        text = re.sub(r"\s*\([^)]*\)", "", text).strip()
        text = re.sub(r"Day\s+(\d+)\s+The\s+", r"Day \1 ", text)
        text = re.sub(r"^Day\s+(\d+)\s+", r"Day \1: ", text)
        cleaned.append(text[0].lower() + text[1:] if text else text)
    return _join_phrases([item for item in cleaned if item])


def _friendly_detail(detail: str) -> str:
    return detail.strip().rstrip(".")


def _topic_label(heading: str) -> str:
    labels = {
        "role and assumptions": "trip assumptions",
        "working context": "travel context",
        "key decisions": "key decisions",
        "plan": "the plan",
        "next steps": "next steps",
    }
    return labels.get(heading.lower().strip(), "")
