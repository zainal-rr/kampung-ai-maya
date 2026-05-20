from __future__ import annotations

import re
from dataclasses import dataclass, field

from browser_control import BrowserController, element_summary, page_summary
from browser_workflows import HumanBrowserWorkflowRouter
from document_actions import DocumentActionRouter
from drawing_actions import DrawingActionRouter
from file_actions import FileActionRouter
from harness_models import GroundedObservation, HarnessArtifact, local_artifact
from imac_workflows import ImacWorkflowRouter
from local_actions import LocalActionRouter
from project_actions import ProjectActionRouter
from screen_service import MacScreenService
from screen_responder import ScreenResponder
from self_healing import self_heal_text
from skill_factory import SkillFactory
from utils import OSBridge
from workspace_actions import WorkspaceActionRouter


SENSITIVE_WORDS = (
    "buy", "book", "pay", "checkout", "purchase", "submit", "passport",
    "card", "confirm", "delete", "send", "upload", "deploy", "restart",
)


@dataclass
class HarnessToolResult:
    status: str
    message: str
    artifacts: list[str] = field(default_factory=list)
    structured_artifacts: list[HarnessArtifact] = field(default_factory=list)
    observation: GroundedObservation | None = None
    requires_approval: bool = False
    next_step: str = ""
    keep_open: bool = False


class HarnessTools:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.browser = HumanBrowserWorkflowRouter(db_path)
        self.documents = DocumentActionRouter(db_path)
        self.drawing = DrawingActionRouter()
        self.files = FileActionRouter()
        self.workspace = WorkspaceActionRouter()
        self.projects = ProjectActionRouter(db_path)
        self.imac = ImacWorkflowRouter(db_path)
        self.local = LocalActionRouter()
        self.screen = ScreenResponder(db_path)
        self.skills = SkillFactory(db_path)

    async def execute(self, workflow_type: str, text: str, channel: str, approved: bool = False) -> HarnessToolResult:
        if workflow_type == "skill":
            return await self._skill(text, channel, approved)
        if not _approval_owned_by_browser(workflow_type, text) and _needs_approval(text) and not approved:
            return HarnessToolResult(
                "paused",
                "This needs your confirmation first.",
                requires_approval=True,
                next_step="approval_gate",
            )
        handler = {
            "browser": self._browser,
            "screen": self._screen,
            "document": self._document,
            "project": self._project,
            "self_heal": self._self_heal,
            "app": self._app,
            "scheduled": self._scheduled,
            "omi_distillation": self._omi_placeholder,
        }.get(workflow_type, self._general)
        return await handler(text, channel)

    async def _browser(self, text: str, channel: str) -> HarnessToolResult:
        reply = await self.browser.handle(text, channel) or await self.imac.handle(text, channel)
        observation = _browser_observation()
        result = _result(reply, "browser")
        result.observation = observation
        result.keep_open = True
        return result

    async def _screen(self, text: str, channel: str) -> HarnessToolResult:
        reply = await self.screen.handle(text, channel)
        result = _result(reply, "screen")
        result.observation = GroundedObservation(
            source="screen",
            screenshot_status="fresh capture requested",
            screen_summary=(reply or "")[:500],
            confidence=0.7 if reply else 0.0,
            provenance=("screen_responder",),
        )
        result.keep_open = True
        return result

    async def _document(self, text: str, channel: str) -> HarnessToolResult:
        reply = (
            await self.documents.handle(text, channel)
            or await self.drawing.handle(text, channel)
            or await self.workspace.handle(text, channel)
            or await self.files.handle(text, channel)
        )
        return _result(reply, "document")

    async def _project(self, text: str, channel: str) -> HarnessToolResult:
        reply = await self.projects.handle(text, channel)
        return _result(reply, "project")

    async def _skill(self, text: str, channel: str, approved: bool = False) -> HarnessToolResult:
        subject = _skill_subject(text)
        if not subject:
            return HarnessToolResult("skipped", "")
        if not approved:
            return HarnessToolResult(
                "paused",
                "I don't have a real skill for that yet. Do you want me to draft the missing skill first?",
                requires_approval=True,
                next_step="skill",
            )
        result = await self.skills.scaffold_skill(subject)
        message = f"Done. I created the skill scaffold for {result['title']} at {result['scaffold_path']}."
        artifact = local_artifact("note", str(result["scaffold_path"]), result["title"], "skill_factory")
        return HarnessToolResult("completed", message, [str(result["scaffold_path"])], [artifact], next_step="skill")

    async def _self_heal(self, text: str, channel: str) -> HarnessToolResult:
        reply = await self_heal_text(self.db_path)
        return HarnessToolResult("completed", reply, next_step="self_heal", keep_open=True)

    async def _app(self, text: str, channel: str) -> HarnessToolResult:
        reply = await self.local.handle(text)
        return _result(reply, "app")

    async def _scheduled(self, text: str, channel: str) -> HarnessToolResult:
        message = text.strip() or "Scheduled workflow completed."
        return HarnessToolResult("completed", message)

    async def _omi_placeholder(self, text: str, channel: str) -> HarnessToolResult:
        return HarnessToolResult("paused", "Omi distillation is prepared, but it stays disabled until the pendant arrives.")

    async def _general(self, text: str, channel: str) -> HarnessToolResult:
        reply = await self.imac.handle(text, channel) or await self.local.handle(text)
        return _result(reply, "general")


def _result(reply: str | None, kind: str) -> HarnessToolResult:
    if not reply:
        return HarnessToolResult("skipped", "")
    artifacts = re.findall(r"\[file:([^\]]+)\]", reply)
    structured = [
        local_artifact(_kind_for_path(path, kind), path, f"{kind} artifact", kind)
        for path in artifacts
    ]
    return HarnessToolResult("completed", reply, artifacts, structured, next_step=kind)


def _needs_approval(text: str) -> bool:
    lowered = " ".join(text.lower().split())
    return any(word in lowered for word in SENSITIVE_WORDS)


def _approval_owned_by_browser(workflow_type: str, text: str) -> bool:
    if workflow_type != "browser":
        return False
    lowered = text.strip().lower()
    return lowered.startswith(("click ", "choose ", "select ", "press ", "fill ", "enter ", "type "))


def _skill_subject(text: str) -> str:
    match = re.search(r"(?:skill|ability|capability)\s+(?:for|to)?\s*(.+)$", text, re.IGNORECASE)
    return match.group(1).strip(" .") if match else text.strip()


def _kind_for_path(path: str, fallback: str) -> str:
    lowered = path.lower()
    if lowered.endswith(".pptx"):
        return "presentation"
    if lowered.endswith(".docx"):
        return "document"
    if lowered.endswith(".svg"):
        return "drawing"
    if lowered.endswith((".jpg", ".jpeg", ".png")):
        return "screenshot"
    if lowered.endswith(".md"):
        return "note"
    return fallback


def _browser_observation() -> GroundedObservation | None:
    try:
        controller = BrowserController()
        page = controller.inspect_page(max_chars=1800)
        elements = controller.inspect_elements(max_items=12)
    except Exception as exc:
        return GroundedObservation(
            source="browser",
            screenshot_status=f"browser unavailable: {exc}",
            confidence=0.2,
            provenance=("browser_control",),
        )
    try:
        bridge = OSBridge()
        frontmost = bridge.get_frontmost_app()
        running = tuple(bridge.list_running_apps())
    except Exception:
        frontmost, running = "", ()
    screen = MacScreenService().capture_once()
    clickable = tuple(f"{item.kind}: {item.label}" for item in elements if item.kind not in {"input", "textarea", "select"})
    fillable = tuple(f"{item.kind}: {item.label}" for item in elements if item.kind in {"input", "textarea", "select"})
    return GroundedObservation(
        source="browser",
        frontmost_app=frontmost,
        running_apps=running,
        page_title=page.title,
        url=page.url,
        text_summary=page_summary(page, max_lines=6),
        clickable_targets=clickable[:8],
        fillable_targets=fillable[:8],
        screenshot_status=screen.status if screen.visible else f"unavailable: {screen.status}",
        screen_summary=element_summary(elements, max_items=8),
        confidence=0.75,
        provenance=("browser_dom", "browser_visible_text", "macos_app_state", "screen_capture"),
    )
