from __future__ import annotations

import re
from dataclasses import dataclass, field

from maya_browser.browser_workflows import HumanBrowserWorkflowRouter
from maya_documents.document_actions import DocumentActionRouter
from maya_core.drawing_actions import DrawingActionRouter
from maya_core.file_actions import FileActionRouter
from maya_harness.harness_browser_observation import agentic_browser_message as _agentic_browser_message
from maya_harness.harness_browser_observation import browser_observation as _browser_observation
from maya_harness.harness_models import GroundedObservation, HarnessArtifact, local_artifact
from maya_core.imac_workflows import ImacWorkflowRouter
from maya_core.local_actions import LocalActionRouter
from maya_core.project_actions import ProjectActionRouter
from maya_core.screen_responder import ScreenResponder
from maya_core.self_heal_execution import execute_checkpointed_self_heal
from maya_core.self_healing import self_heal_from_complex_plan, self_heal_text
from maya_core.skill_factory import SkillFactory
from maya_core.untrusted_input_boundary import assess_untrusted_context
from maya_core.workspace_actions import WorkspaceActionRouter


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
    model_lane: str = ""
    cost_recorded: bool = False


class HarnessTools:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._browser_router: HumanBrowserWorkflowRouter | None = None
        self.documents = DocumentActionRouter(db_path)
        self.drawing = DrawingActionRouter()
        self.files = FileActionRouter()
        self.workspace = WorkspaceActionRouter()
        self.projects = ProjectActionRouter(db_path)
        self.imac = ImacWorkflowRouter(db_path)
        self.local = LocalActionRouter()
        self.screen = ScreenResponder(db_path)
        self.skills = SkillFactory(db_path)

    @property
    def browser(self) -> HumanBrowserWorkflowRouter:
        if self._browser_router is None:
            self._browser_router = HumanBrowserWorkflowRouter(self.db_path)
        return self._browser_router

    @browser.setter
    def browser(self, router: HumanBrowserWorkflowRouter) -> None:
        self._browser_router = router

    async def execute(self, workflow_type: str, text: str, channel: str, approved: bool = False, state: dict | None = None) -> HarnessToolResult:
        if workflow_type == "skill":
            return await self._skill(text, channel, approved)
        agentic_read_action = _agentic_read_action(state)
        agentic_local_create_action = _agentic_local_create_action(state)
        if not agentic_read_action and not agentic_local_create_action and not _approval_owned_by_browser(workflow_type, text) and _needs_approval(text) and not approved:
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
        if workflow_type == "self_heal":
            return await self._self_heal(text, channel, state or {})
        if workflow_type == "browser":
            return await self._browser(text, channel, state or {})
        effective_channel = _effective_channel_for_agentic(workflow_type, channel, state)
        return await handler(text, effective_channel)

    async def _browser(self, text: str, channel: str, state: dict | None = None) -> HarnessToolResult:
        state = state or {}
        effective_channel = "imac" if state.get("agentic_loop") and channel == "telegram" else channel
        reply = await self.browser.handle(text, effective_channel) or await self.imac.handle(text, effective_channel)
        agentic = bool(state.get("agentic_loop"))
        observation = _browser_observation(
            max_chars=4500 if agentic else 1800,
            max_lines=18 if agentic else 6,
            max_targets=12 if agentic else 8,
        )
        result = _result(reply, "browser")
        result.observation = observation
        if agentic and observation:
            result.message = _agentic_browser_message(observation, fallback=reply or "")
        if observation and observation.url:
            result.structured_artifacts.append(
                HarnessArtifact(
                    kind="browser_page",
                    url=observation.url,
                    summary=observation.page_title or "browser page",
                    source_tool="browser_control",
                    exists_status="observed",
                )
            )
        result.keep_open = not agentic
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
            **_untrusted_kwargs(reply or "", "screen", "screen_responder"),
        )
        result.keep_open = True
        return result

    async def _document(self, text: str, channel: str) -> HarnessToolResult:
        reply = (
            await self.documents.handle(text, channel)
            or (await self.drawing.handle(text, channel) if _wants_drawing(text) else None)
            or (await self.workspace.handle(text, channel) if _wants_workspace(text) else None)
            or (await self.files.handle(text, channel) if _wants_raw_file(text) else None)
        )
        result = _result(reply, "document")
        if getattr(self.documents, "last_model_lane", ""):
            result.model_lane = self.documents.last_model_lane
            result.cost_recorded = self.documents.last_cost_recorded
        return result

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

    async def _self_heal(self, text: str, channel: str, state: dict | None = None) -> HarnessToolResult:
        state = state or {}
        if state.get("source_complex_run_id") and state.get("complex_plan"):
            if not state.get("self_heal_checkpoint"):
                await self_heal_from_complex_plan(
                    self.db_path,
                    request=str(state.get("complex_request") or text),
                    plan=str(state.get("complex_plan") or ""),
                    review=str(state.get("complex_review") or ""),
                )
            execution = await execute_checkpointed_self_heal(self.db_path, state)
            return HarnessToolResult(
                execution["status"],
                execution["message"],
                list(execution.get("artifacts") or []),
                requires_approval=bool(execution.get("requires_approval")),
                next_step="self_heal",
                keep_open=bool(execution.get("requires_approval")),
            )
        else:
            reply = await self_heal_text(self.db_path, create_review_task=False, issue_hint=text)
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
    artifacts = _artifact_paths_from_reply(reply)
    structured = [
        local_artifact(_kind_for_path(path, kind), path, f"{kind} artifact", kind)
        for path in artifacts
    ]
    return HarnessToolResult("completed", reply, artifacts, structured, next_step=kind)


def _needs_approval(text: str) -> bool:
    lowered = " ".join(text.lower().split())
    return any(word in lowered for word in SENSITIVE_WORDS)


def _wants_drawing(text: str) -> bool:
    lowered = " ".join(text.lower().split())
    return lowered.startswith(("draw ", "create drawing", "make drawing"))


def _wants_workspace(text: str) -> bool:
    lowered = " ".join(text.lower().split())
    return "folder" in lowered or lowered.startswith(("create project", "make project", "start project"))


def _wants_raw_file(text: str) -> bool:
    lowered = " ".join(text.lower().split())
    return bool(re.match(r"^(create|write)(?: a)? file\s+.+\s+with\s+.+$", lowered))


def _approval_owned_by_browser(workflow_type: str, text: str) -> bool:
    if workflow_type != "browser":
        return False
    lowered = text.strip().lower()
    return lowered.startswith(("click ", "choose ", "select ", "press ", "fill ", "enter ", "type "))


def _agentic_read_action(state: dict | None) -> bool:
    if not state or not state.get("agentic_loop"):
        return False
    action = dict(state.get("planned_action") or {})
    tool_name = str(action.get("tool") or "")
    normalized = tool_name.replace("_", ".", 1) if "." not in tool_name else tool_name
    return normalized in {"browser.inspect", "screen.capture"}


def _agentic_local_create_action(state: dict | None) -> bool:
    if not state or not state.get("agentic_loop"):
        return False
    action = dict(state.get("planned_action") or {})
    tool_name = str(action.get("tool") or "")
    normalized = tool_name.replace("_", ".", 1) if "." not in tool_name else tool_name
    return normalized in {"docx.create", "xlsx.create", "pptx.create", "file.create"}


def _effective_channel_for_agentic(workflow_type: str, channel: str, state: dict | None) -> str:
    if channel != "telegram" or workflow_type != "document":
        return channel
    if _agentic_local_create_action(state):
        return "imac"
    return channel


def _skill_subject(text: str) -> str:
    match = re.search(r"(?:skill|ability|capability)\s+(?:for|to)?\s*(.+)$", text, re.IGNORECASE)
    return match.group(1).strip(" .") if match else text.strip()


def _kind_for_path(path: str, fallback: str) -> str:
    lowered = path.lower()
    if lowered.endswith(".pptx"):
        return "presentation"
    if lowered.endswith(".xlsx"):
        return "spreadsheet"
    if lowered.endswith(".docx"):
        return "document"
    if lowered.endswith(".svg"):
        return "drawing"
    if lowered.endswith((".jpg", ".jpeg", ".png")):
        return "screenshot"
    if lowered.endswith(".md"):
        return "note"
    return fallback


def _artifact_paths_from_reply(reply: str) -> list[str]:
    paths = list(re.findall(r"\[file:([^\]]+)\]", reply))
    for match in re.findall(r"(/Users/[^\n\r]+?\.(?:docx|xlsx|pptx|md|html|png|svg|pdf))", reply):
        path = match.strip().rstrip(".,)")
        if path not in paths:
            paths.append(path)
    return paths


def _untrusted_kwargs(text: str, source: str, source_id: str = "") -> dict[str, object]:
    context = assess_untrusted_context(text, source=source, source_id=source_id)
    return {
        "untrusted_influence": context.untrusted_influence,
        "injection_detected": context.injection_detected,
        "untrusted_source": context.source,
        "untrusted_signals": context.risk_notes,
    }
