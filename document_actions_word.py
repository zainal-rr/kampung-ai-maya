from __future__ import annotations

from document_actions_context import *
from document_actions_content_helpers import _attach
from document_actions_word_helpers import (
    _backup_word_file,
    _edited_word_topic,
    _router_putty_repair_markdown,
    _router_putty_topic,
    _word_document_title,
    _word_edit_request,
    _word_repair_request,
)


class DocumentWordMixin:
    async def _create_word(self, topic: str, project_scoped: bool, channel: str) -> str:
        preflight = await self._artifact_preflight("docx", topic)
        self.last_model_lane = f"{preflight.lane_prefix} + Gemini Flash role-based Word draft"
        self.last_cost_recorded = preflight.cost_recorded
        path = await self._path("docx", topic, project_scoped)
        if not path_allowed(path):
            return f"I can't write to {path}."
        try:
            draft = await self._draft_markdown(topic, preflight)
        except Exception as exc:
            return document_generation_failed("Word document", exc)
        if not draft:
            return document_generation_failed("Word document", RuntimeError("Gemini returned no document content."))
        self.last_model_lane = (
            f"{preflight.lane_prefix} + Gemini Flash grounded role-based Word draft"
            if draft.grounded else f"{preflight.lane_prefix} + Gemini Flash role-based Word draft"
        )
        self.last_cost_recorded = True
        await self._build_word_doc(path, topic, draft.content)
        quality = await self._word_quality(path, topic)
        if not quality.passed:
            repaired = await self._repair_word_doc(path, topic, quality)
            if repaired:
                quality = await self._word_quality(path, topic)
        await self._remember(path, f"Created Word draft: {quality.summary}", project_scoped)
        if not quality.passed:
            return await self._draft_with_issues("Word draft", path, channel, "Microsoft Word", quality.short_issue_text())
        return await self._done("Word draft", path, channel, "Microsoft Word")

    async def _build_word_doc(self, path: Path, topic: str, markdown: str) -> None:
        sections = strengthen_word_sections(topic, word_sections_from_markdown(markdown, topic))
        sections = await style_sections(self.db_path, sections)
        await asyncio.to_thread(create_docx, path, _word_document_title(topic), sections)

    async def _word_quality(self, path: Path, topic: str) -> ArtifactQualityResult:
        local_qa = await asyncio.to_thread(validate_docx_path, path, topic)
        if "local Word QA" not in self.last_model_lane:
            self.last_model_lane += " + local Word QA"
        review_qa = await review_artifact_quality(self.db_path, "docx", topic, await asyncio.to_thread(extract_docx_text, path))
        if review_qa.review_model and "Claude Word review" not in self.last_model_lane:
            self.last_model_lane += " + Claude Word review"
        elif review_qa.warnings and "Claude Word review" not in self.last_model_lane:
            self.last_model_lane += " + Claude Word review skipped"
        return local_qa.merge(review_qa)

    async def _repair_word_doc(self, path: Path, topic: str, quality: ArtifactQualityResult) -> bool:
        if _router_putty_topic(topic):
            await self._build_word_doc(path, "Router Setup Guide With PuTTY Config", _router_putty_repair_markdown())
            if "Word deterministic PuTTY repair" not in self.last_model_lane:
                self.last_model_lane += " + Word deterministic PuTTY repair"
            return True
        try:
            current = await asyncio.to_thread(extract_docx_text, path)
            repair_topic = _word_repair_request(topic, quality.short_issue_text(), current)
            preflight = await self._artifact_preflight("docx", topic)
            draft = await self._draft_markdown(repair_topic, preflight)
        except Exception as exc:
            logger.warning("Word repair pass failed for %r: %s", topic, exc)
            return False
        if not draft:
            return False
        await self._build_word_doc(path, topic, draft.content)
        if "Word repair pass" not in self.last_model_lane:
            self.last_model_lane += " + Word repair pass"
        self.last_cost_recorded = True
        return True

    async def _edit_latest_document(self, instruction: str, channel: str, *, save_copy: bool = False) -> str:
        raw = await get_preference(self.db_path, LAST_DOC_KEY)
        if not raw:
            return "Tell me which document to update first."
        path = Path(raw)
        if not path.exists():
            return f"I cannot find the last document at {path}."
        if path.suffix.lower() != ".docx":
            return "I can edit the latest Word document first. Excel and PowerPoint editing are still separate work."
        if action_permission("edit_document") != "allow":
            return "I need your confirmation before editing that document."
        try:
            current = await asyncio.to_thread(extract_docx_text, path)
            topic = _edited_word_topic(path, instruction, current)
            preflight = await self._artifact_preflight("docx", topic)
            self.last_model_lane = f"{preflight.lane_prefix} + Gemini Flash Word edit"
            self.last_cost_recorded = preflight.cost_recorded
            draft = await self._draft_markdown(_word_edit_request(topic, instruction, current), preflight)
        except Exception as exc:
            return document_generation_failed("Word document edit", exc)
        if not draft:
            return document_generation_failed("Word document edit", RuntimeError("Gemini returned no edited document content."))
        target = versioned_path(path) if save_copy else path
        backup = await asyncio.to_thread(_backup_word_file, path)
        await self._build_word_doc(target, topic, draft.content)
        quality = await self._word_quality(target, topic)
        if not quality.passed:
            repaired = await self._repair_word_doc(target, topic, quality)
            if repaired:
                quality = await self._word_quality(target, topic)
        if not quality.passed:
            if save_copy and target.exists():
                await asyncio.to_thread(target.unlink)
            elif backup:
                await asyncio.to_thread(shutil.copy2, backup, path)
            if "Word edit restore" not in self.last_model_lane:
                self.last_model_lane += " + Word edit restore"
            await upsert_preference(self.db_path, LAST_DOC_KEY, str(path), source="document")
            return _attach(
                f"I tried to update the latest Word document, but QA failed: {quality.short_issue_text()}. I kept the original unchanged.",
                path,
                channel,
            )
        await self._remember(target, f"Edited Word draft: {quality.summary}", False)
        if not quality.passed:
            return await self._draft_with_issues("edited Word draft", target, channel, "Microsoft Word", quality.short_issue_text())
        label = "edited Word copy" if save_copy else "updated Word document"
        reply = await self._done(label, target, channel, "Microsoft Word")
        if not save_copy and backup:
            prefix = "Done. I updated the latest Word document in place. I kept an internal backup before editing."
            if channel == "telegram":
                return _attach(prefix, target, channel)
            return prefix if "opened it on the iMac" not in reply else f"{prefix} I opened it on the iMac."
        return reply
