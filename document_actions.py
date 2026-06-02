from __future__ import annotations

from document_actions_context import *
from document_actions_content_helpers import (
    _append_text,
    _artifact_kind,
    _attach,
    _budget_rows,
    _should_defer_html_app_to_artisan,
)
from document_actions_word_helpers import _document_edit_request
from document_actions_html import DocumentHtmlMixin
from document_actions_office import DocumentOfficeMixin
from document_actions_word import DocumentWordMixin


_PATCHABLE_SYMBOLS = (
    "artifact_preflight_with_gemini",
    "create_powerpoint_with_qa",
    "draft_html_with_gemini",
    "draft_html_with_kimi",
    "draft_markdown_with_gemini",
    "review_artifact_quality",
    "review_html_app",
    "review_presentation_slides",
    "should_use_model_draft",
    "style_document_text",
    "style_sections",
    "style_table",
)


def _sync_patchable_symbols() -> None:
    import sys
    import document_actions_context
    import document_actions_html
    import document_actions_office
    import document_actions_word

    current = sys.modules[__name__]
    modules = (document_actions_context, document_actions_html, document_actions_office, document_actions_word)
    for name in _PATCHABLE_SYMBOLS:
        if hasattr(current, name):
            value = getattr(current, name)
            for module in modules:
                if hasattr(module, name):
                    setattr(module, name, value)


class DocumentActionRouter(DocumentHtmlMixin, DocumentWordMixin, DocumentOfficeMixin):
    def __init__(self, db_path: str, workspace: Path | None = None, bridge: OSBridge | None = None):
        self.db_path = db_path
        self.workspace = workspace or workspace_dir("")
        self.bridge = bridge or OSBridge()
        self.visual_workflow = VisualWorkflowRenderer(db_path, self.bridge)
        self.last_model_lane = ""
        self.last_cost_recorded = False

    async def handle(self, text: str, channel: str) -> str | None:
        _sync_patchable_symbols()
        visual = await self.visual_workflow.handle(text, channel)
        if visual:
            self.last_model_lane = "Local visual workflow renderer"
            self.last_cost_recorded = False
            return visual
        update = markdown_update(text)
        if update:
            return await self._update_markdown(update, channel)
        edit = _document_edit_request(text)
        if edit:
            instruction, save_copy = edit
            return await self._edit_latest_document(instruction, channel, save_copy=save_copy)
        request = document_request(text)
        if request is None:
            return None
        kind, topic, project_scoped = request
        if project_scoped and not await active_project(self.db_path):
            return "No active project yet. Open or create a project first, then I can put it under that project's docs folder."
        if contains_sensitive_info(topic):
            return hard_no_private_exposure_text()
        if action_permission("create_document" if kind != "pptx" else "create_presentation") != "allow":
            return "I need your confirmation before creating that document."
        question = artifact_parameter_question(kind, topic, channel)
        if question:
            self.last_model_lane = "clarification"
            self.last_cost_recorded = False
            return question
        if kind == "md":
            return await self._create_markdown(topic, project_scoped, channel)
        if kind == "html":
            if _should_defer_html_app_to_artisan(text):
                return None
            return await self._create_html(topic, project_scoped, channel)
        if kind == "docx":
            return await self._create_word(topic, project_scoped, channel)
        if kind == "xlsx":
            return await self._create_excel(topic, project_scoped, channel)
        return await self._create_powerpoint(topic, channel)

    async def _update_markdown(self, note: str, channel: str) -> str:
        path = await self._markdown_target()
        if path is None:
            return "Tell me which Markdown file to update first."
        if contains_sensitive_info(note):
            return hard_no_private_exposure_text()
        if path.suffix.lower() != ".md":
            return "The last document is not a Markdown file, so I will not edit it this way."
        note = await style_document_text(self.db_path, note.strip())
        addition = f"\n\n## Update\n\n{note}\n"
        await asyncio.to_thread(_append_text, path, addition)
        await upsert_preference(self.db_path, LAST_DOC_KEY, str(path), source="document")
        return _attach(f"Done. I updated the Markdown file at {path}.", path, channel)

    async def _path(self, kind: str, topic: str, project_scoped: bool) -> Path:
        project = await active_project(self.db_path) if project_scoped else None
        if project:
            return named_artifact_path(project.path / "docs", topic, kind)
        folder = {"md": "notes", "html": "artifacts", "docx": "documents", "xlsx": "spreadsheets"}.get(kind, "documents")
        return named_artifact_path(self.workspace / folder, topic, kind)

    async def _remember(self, path: Path, action: str, project_scoped: bool) -> None:
        await upsert_preference(self.db_path, LAST_DOC_KEY, str(path), source="document")
        await record_structured_artifact(
            self.db_path,
            DIRECT_DOC_RUN_ID,
            local_artifact(_artifact_kind(path), str(path), action, "document_actions"),
        )
        project = await active_project(self.db_path) if project_scoped else None
        if project:
            await remember_project_note(self.db_path, project.path, "document", f"{action}: {path.name}")

    async def _artifact_preflight(self, artifact_type: str, topic: str) -> ArtifactPreflight:
        preflight = await artifact_preflight_with_gemini(self.db_path, artifact_type, topic)
        if preflight.cost_recorded:
            self.last_cost_recorded = True
        return preflight

    async def _draft_markdown(self, topic: str, preflight: ArtifactPreflight | None = None) -> MarkdownDraft | None:
        context = preflight.content if preflight else ""
        if not context:
            return await draft_markdown_with_gemini(self.db_path, topic)
        try:
            signature = inspect.signature(draft_markdown_with_gemini)
            supports_context = any(
                param.kind == inspect.Parameter.VAR_POSITIONAL
                for param in signature.parameters.values()
            ) or len(signature.parameters) >= 3
        except (TypeError, ValueError):
            supports_context = False
        if supports_context:
            return await draft_markdown_with_gemini(self.db_path, topic, context)
        return await draft_markdown_with_gemini(self.db_path, topic)

    async def _draft_with_issues(self, label: str, path: Path, channel: str, app_name: str | None, issues: str) -> str:
        message = f"I created a {label} at {path}, but QA found: {issues}. I’m keeping it as a draft."
        if channel == "imac":
            try:
                opened_app = await asyncio.to_thread(open_created_file, path, self.bridge, app_name)
                suffix = f" in {opened_app}" if opened_app else ""
                return f"{message} I opened it on the iMac{suffix}."
            except Exception as exc:
                return f"{message} I could not open it: {exc}"
        return _attach(message, path, channel)

    async def _done(self, label: str, path: Path, channel: str, app_name: str | None) -> str:
        article = "an" if label.lower().startswith("excel") else "a"
        message = f"Done. I created {article} {label} at {path}."
        if channel == "imac":
            try:
                opened_app = await asyncio.to_thread(open_created_file, path, self.bridge, app_name)
                suffix = f" in {opened_app}" if opened_app else ""
                return f"{message} I opened it on the iMac{suffix}."
            except Exception as exc:
                return f"{message} I could not open it: {exc}"
        return _attach(f"Done. I created {article} {label}.", path, channel)

    async def _markdown_target(self) -> Path | None:
        raw = await get_preference(self.db_path, LAST_DOC_KEY)
        return Path(raw) if raw else None
