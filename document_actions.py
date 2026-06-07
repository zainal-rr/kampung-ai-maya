"""Canonical document/action router shared by Telegram and iMac.

This router is the main entry point for user requests that may create, edit, or
send artifacts. It coordinates local parsing, pending clarification state,
semantic intent resolution, discourse-topic carryover, and the type-specific
mixins for Word, Excel, PowerPoint, Markdown, HTML, and local file delivery.

The key design rule is channel-neutral creation and channel-specific delivery:
Telegram and iMac should hit the same builders and QA gates, then diverge only
when attaching a Telegram file versus opening/focusing a native iMac app.
"""

from __future__ import annotations

from document_actions_context import *
from artifact_retry_policy import artifact_qa_max_attempts, qa_retry_exhausted_message
from document_actions_content_helpers import (
    _append_text,
    _artifact_kind,
    _attach,
    _budget_rows,
    _should_defer_html_app_to_artisan,
)
from document_actions_word_helpers import _document_edit_request
from artifact_clarification_state import consume_pending_artifact_request, save_pending_artifact_request
from artifact_discourse_context import resolve_referenced_artifact_topic
from artifact_semantic_enrichment import enrich_artifact_topic
from artifact_semantic_resolver import resolve_semantic_artifact_intent
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
        pending = await consume_pending_artifact_request(self.db_path, channel, text)
        if pending:
            kind, topic = pending
            return await self._handle_document_request(kind, topic, False, channel)
        edit = _document_edit_request(text)
        if edit:
            instruction, save_copy = edit
            return await self._edit_latest_document(instruction, channel, save_copy=save_copy)
        request = document_request(text)
        if request is None:
            semantic = await resolve_semantic_artifact_intent(self.db_path, text)
            if semantic:
                if semantic.action == "clarify":
                    await save_pending_artifact_request(self.db_path, channel, text)
                    self.last_model_lane = semantic.lane or "semantic clarification"
                    self.last_cost_recorded = semantic.cost_recorded
                    return semantic.question
                if semantic.action == "edit":
                    reply = await self._edit_latest_document(semantic.instruction, channel, save_copy=semantic.save_copy)
                    self._prepend_semantic_lane(semantic)
                    return reply
                if semantic.action == "create":
                    request = (semantic.kind, semantic.topic, False)
                    self._pending_semantic_lane = semantic
            if request is not None:
                pass
            else:
                clarification = artifact_intent_clarification(text)
                if clarification:
                    await save_pending_artifact_request(self.db_path, channel, text)
                    self.last_model_lane = "clarification"
                    self.last_cost_recorded = False
                    return clarification
                return None
        else:
            kind, topic, project_scoped = request
            topic = await resolve_referenced_artifact_topic(self.db_path, channel, topic, text)
            enriched_topic, _domain, _parameters = enrich_artifact_topic(kind, topic, text)
            request = (kind, enriched_topic, project_scoped)
        pending_semantic = getattr(self, "_pending_semantic_lane", None)
        if pending_semantic is not None:
            self._pending_semantic_lane = None
            kind, topic, project_scoped = request
            topic = await resolve_referenced_artifact_topic(self.db_path, channel, topic, text)
            reply = await self._handle_document_request(kind, topic, project_scoped, channel)
            self._prepend_semantic_lane(pending_semantic)
            return reply
        return await self._handle_document_request(*request, channel)

    async def _handle_document_request(self, kind: str, topic: str, project_scoped: bool, channel: str) -> str:
        if kind == "clarify":
            return topic
        if project_scoped and not await active_project(self.db_path):
            return "No active project yet. Open or create a project first, then I can put it under that project's docs folder."
        if contains_sensitive_info(topic):
            return hard_no_private_exposure_text()
        if action_permission("create_document" if kind != "pptx" else "create_presentation") != "allow":
            return "I need your confirmation before creating that document."
        resolution = await resolve_artifact_parameters(self.db_path, kind, topic, channel)
        if resolution.question:
            self.last_model_lane = "clarification"
            self.last_cost_recorded = False
            return resolution.question
        topic = resolution.topic
        question = artifact_parameter_question(kind, topic, channel)
        if question:
            self.last_model_lane = "clarification"
            self.last_cost_recorded = False
            return question
        if kind == "md":
            return await self._create_markdown(topic, project_scoped, channel)
        if kind == "html":
            if _should_defer_html_app_to_artisan(topic):
                return None
            return await self._create_html(topic, project_scoped, channel)
        if kind == "docx":
            return await self._create_word(topic, project_scoped, channel)
        if kind == "xlsx":
            return await self._create_excel(topic, project_scoped, channel)
        return await self._create_powerpoint(topic, channel)

    def _prepend_semantic_lane(self, semantic) -> None:
        if not getattr(semantic, "lane", ""):
            return
        if self.last_model_lane:
            if semantic.lane not in self.last_model_lane:
                self.last_model_lane = f"{semantic.lane} + {self.last_model_lane}"
        else:
            self.last_model_lane = semantic.lane
        self.last_cost_recorded = self.last_cost_recorded or bool(getattr(semantic, "cost_recorded", False))

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

    async def _remember(
        self,
        path: Path,
        action: str,
        project_scoped: bool,
        channel: str = "imac",
        artifact_type: str = "",
        topic: str = "",
    ) -> None:
        await upsert_preference(self.db_path, LAST_DOC_KEY, str(path), source="document")
        await upsert_preference(self.db_path, LAST_DRAFT_DOC_KEY, "", source="document")
        if topic:
            await record_artifact_session(self.db_path, channel, artifact_type or path.suffix.lower().lstrip("."), path, topic)
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
        await upsert_preference(self.db_path, LAST_DRAFT_DOC_KEY, str(path), source="document")
        suffix = path.suffix.lower().lstrip(".") or label
        return qa_retry_exhausted_message(label, artifact_qa_max_attempts(suffix))

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
