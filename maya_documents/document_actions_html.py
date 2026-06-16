from __future__ import annotations

from maya_documents.document_actions_context import *
from maya_documents.document_actions_content_helpers import _html_content, _looks_like_html_app


class DocumentHtmlMixin:
    async def _create_markdown(self, topic: str, project_scoped: bool, channel: str) -> str:
        self.last_model_lane = ""
        self.last_cost_recorded = False
        path = await self._path("md", topic, project_scoped)
        try:
            content = await self._markdown_content(topic)
            content = await style_document_text(self.db_path, content)
        except Exception as exc:
            return document_generation_failed("Markdown file", exc)
        if not path_allowed(path):
            return f"I can't write to {path}."
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_text, content, "utf-8")
        await self._remember(path, "Created Markdown draft", project_scoped, channel, "md", topic)
        return await self._done("Markdown draft", path, channel, app_name=None)

    async def _create_html(self, topic: str, project_scoped: bool, channel: str) -> str:
        self.last_model_lane = html_builder_lane()
        self.last_cost_recorded = False
        path = await self._path("html", topic, project_scoped)
        draft, lane = await self._html_draft(topic)
        if not draft:
            return document_generation_failed("HTML file", RuntimeError("Codex app lane and Gemini returned no usable HTML app."))
        self.last_model_lane = lane
        self.last_cost_recorded = True
        content = _html_content(draft.content, topic)
        if not _looks_like_html_app(content):
            fallback = await self._html_fallback(topic)
            if not fallback:
                return document_generation_failed("HTML file", RuntimeError("Codex app lane and Gemini returned a document instead of an app."))
            content, self.last_model_lane = fallback
        reviewed_content, review_status = await review_html_app(self.db_path, topic, content)
        review_rejected = False
        if review_status == "reviewed" and _looks_like_html_app(reviewed_content):
            content = reviewed_content
            self.last_model_lane += " + Claude HTML review"
        elif review_status in {"reviewed", "rejected"}:
            self.last_model_lane += " + Claude HTML review rejected"
            review_rejected = True
        elif review_status == "failed":
            self.last_model_lane += " + Claude HTML review failed"
        html_qa = validate_html_content(topic, content)
        self.last_model_lane += " + local HTML QA"
        if not path_allowed(path):
            return f"I can't write to {path}."
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_text, content, "utf-8")
        if review_rejected:
            return await self._draft_with_issues("HTML draft", path, channel, None, "Claude HTML review rejected the file")
        if not html_qa.passed:
            return await self._draft_with_issues("HTML draft", path, channel, None, html_qa.short_issue_text())
        await self._remember(path, f"Created HTML app: {html_qa.summary}", project_scoped, channel, "html", topic)
        return await self._done("HTML file", path, channel, app_name=None)

    async def _html_draft(self, topic: str) -> tuple[MarkdownDraft | None, str]:
        primary_failure = ""
        primary_lane = html_builder_lane()
        try:
            draft = await draft_html_with_artisan(self.db_path, topic)
        except TimeoutError as exc:
            logger.warning("%s failed for %r: %s: %s", primary_lane, topic, type(exc).__name__, exc)
            draft = None
            primary_failure = f"{primary_lane} timeout -> "
        except Exception as exc:
            logger.warning("%s failed for %r: %s: %s", primary_lane, topic, type(exc).__name__, exc)
            draft = None
            primary_failure = f"{primary_lane} failed -> "
        if draft:
            return draft, primary_lane
        logger.info("Using Gemini HTML fallback for %r", topic)
        fallback = await self._html_fallback(topic)
        if not fallback:
            return None, primary_lane
        content, lane = fallback
        return MarkdownDraft(content), f"{primary_failure}{lane}" if primary_failure else lane

    async def _html_fallback(self, topic: str) -> tuple[str, str] | None:
        try:
            draft = await draft_html_with_gemini(self.db_path, topic)
        except Exception as exc:
            logger.warning("Gemini HTML fallback failed for %r: %s", topic, exc)
            return None
        if not draft:
            return None
        content = _html_content(draft.content, topic)
        if not _looks_like_html_app(content):
            return None
        return content, "Gemini Flash HTML fallback"

    async def _markdown_content(self, topic: str) -> str:
        if should_use_model_draft(topic):
            self.last_model_lane = "Gemini Flash role-based document draft"
            self.last_cost_recorded = False
            draft = await draft_markdown_with_gemini(self.db_path, topic)
            if draft:
                self.last_model_lane = "Gemini Flash grounded role-based document draft" if draft.grounded else "Gemini Flash role-based document draft"
                self.last_cost_recorded = True
                return draft.content
            raise RuntimeError("Gemini returned no document content.")
        raise RuntimeError("Document generation requires Gemini Flash.")
