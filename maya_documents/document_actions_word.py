from __future__ import annotations

from maya_documents.document_actions_context import *
from maya_documents.artifact_file_state import artifact_changed_since_recorded
from maya_documents.artifact_retry_policy import artifact_qa_max_attempts
from maya_documents.document_actions_content_helpers import _attach
from maya_documents.document_actions_word_helpers import (
    _backup_word_file,
    _draft_override_requested,
    _edited_word_topic,
    _generic_technical_troubleshooting_repair_markdown,
    _generic_technical_troubleshooting_topic,
    _preserve_failed_word_draft,
    _router_network_repair_markdown,
    _router_network_topic,
    _router_putty_repair_markdown,
    _router_putty_topic,
    _word_quality_hard_blocks,
    _word_document_title,
    _word_edit_request,
    _word_repair_request,
)
from maya_voice.artifact_manifest import (
    apply_current_manifest_count_sections,
    current_manifest_title,
    record_current_render_report_for_sections,
)
from maya_core.recent_questions_document import recent_user_questions
from word_simple_edit import apply_simple_docx_edit, simple_docx_edit_instruction


class DocumentWordMixin:
    async def _create_recent_questions_word(self, count: int, project_scoped: bool, channel: str) -> str:
        questions = await recent_user_questions(self.db_path, count=count)
        if not questions:
            return "I could not find recent questions in the conversation history yet."
        topic = f"last {len(questions)} questions"
        path = await self._path("docx", topic, project_scoped)
        if not path_allowed(path):
            return f"I can't write to {path}."
        sections = [
            (
                "Captured Questions",
                [f"{idx}. {question}" for idx, question in enumerate(questions, start=1)],
            )
        ]
        await asyncio.to_thread(create_docx, path, "Last Questions", sections)
        self.last_model_lane = "Local recent-question Word export"
        self.last_cost_recorded = False
        await self._remember(path, f"Created Word export: {len(questions)} recent questions", project_scoped, channel, "docx", topic)
        return await self._done("Word draft", path, channel, "Microsoft Word")

    async def _create_word(self, topic: str, project_scoped: bool, channel: str) -> str:
        preflight = await self._artifact_preflight("docx", topic)
        doc_kind = getattr(preflight, "doc_kind", "generic_document")
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
        quality = await self._word_quality(path, topic, attempt_number=1, doc_kind=doc_kind)
        attempts = 1
        max_attempts = artifact_qa_max_attempts("docx")
        while not quality.passed and attempts < max_attempts:
            attempts += 1
            repaired = await self._repair_word_doc(path, topic, quality, attempts)
            if not repaired:
                break
            quality = await self._word_quality(path, topic, attempt_number=attempts, doc_kind=doc_kind)
        if not quality.passed:
            return await self._draft_with_issues("Word draft", path, channel, "Microsoft Word", quality.short_issue_text(), attempts=attempts, topic=topic)
        await self._remember(path, f"Created Word draft: {quality.summary}", project_scoped, channel, "docx", topic)
        return await self._done("Word draft", path, channel, "Microsoft Word")

    async def _build_word_doc(self, path: Path, topic: str, markdown: str) -> None:
        sections = strengthen_word_sections(topic, word_sections_from_markdown(markdown, topic))
        sections = await apply_current_manifest_count_sections(sections)
        sections = await style_sections(self.db_path, sections)
        title = await current_manifest_title(_word_document_title(topic))
        await asyncio.to_thread(create_docx, path, title, sections)
        await record_current_render_report_for_sections(path, sections)

    async def _word_quality(
        self,
        path: Path,
        topic: str,
        *,
        attempt_number: int = 1,
        doc_kind: str = "generic_document",
    ) -> ArtifactQualityResult:
        local_qa = await asyncio.to_thread(validate_docx_path, path, topic, doc_kind=doc_kind)
        if "local Word QA" not in self.last_model_lane:
            self.last_model_lane += " + local Word QA"
        if "word visual layout" in local_qa.validation_steps and "local Word visual QA" not in self.last_model_lane:
            self.last_model_lane += " + local Word visual QA"
        extracted = await asyncio.to_thread(extract_docx_text, path)
        review_qa = await review_artifact_quality(self.db_path, "docx", topic, extracted)
        if review_qa.review_model and "Claude Word review" not in self.last_model_lane:
            self.last_model_lane += " + Claude Word review"
        elif review_qa.warnings and "Claude Word review" not in self.last_model_lane:
            self.last_model_lane += " + Claude Word review skipped"
        local_qa = await resolve_quality_disagreement(
            self.db_path,
            artifact_type="docx",
            topic=topic,
            path=path,
            local_qa=local_qa,
            review_qa=review_qa,
            extracted=extracted,
            attempt_number=attempt_number,
        )
        return local_qa.merge(review_qa)

    async def _repair_word_doc(self, path: Path, topic: str, quality: ArtifactQualityResult, attempt: int = 2) -> bool:
        if _router_putty_topic(topic):
            await self._build_word_doc(path, "Router Setup Guide With PuTTY Config", _router_putty_repair_markdown())
            if "Word deterministic PuTTY repair" not in self.last_model_lane:
                self.last_model_lane += " + Word deterministic PuTTY repair"
            return True
        if _router_network_topic(topic):
            await self._build_word_doc(path, "Router And WiFi Setup Guide", _router_network_repair_markdown())
            if "Word deterministic router repair" not in self.last_model_lane:
                self.last_model_lane += " + Word deterministic router repair"
            return True
        if _generic_technical_troubleshooting_topic(topic):
            await self._build_word_doc(path, "Technical Troubleshooting Guide", _generic_technical_troubleshooting_repair_markdown())
            if "Word deterministic technical repair" not in self.last_model_lane:
                self.last_model_lane += " + Word deterministic technical repair"
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
        marker = f"Word repair pass {attempt}"
        if marker not in self.last_model_lane:
            self.last_model_lane += f" + {marker}"
        self.last_cost_recorded = True
        return True

    async def _edit_latest_document(self, instruction: str, channel: str, *, save_copy: bool = False) -> str:
        raw = await get_preference(self.db_path, LAST_DOC_KEY)
        if not raw:
            return "Tell me which document to update first."
        path = Path(raw)
        if not path.exists():
            return f"I cannot find the last document at {path}."
        manual_changed = False
        if not save_copy:
            manual_changed = await artifact_changed_since_recorded(self.db_path, path)
            if manual_changed:
                save_copy = True
        suffix = path.suffix.lower()
        if suffix == ".pptx":
            reply = await self._edit_latest_powerpoint(path, instruction, channel, save_copy=save_copy)
            return _manual_edit_safety_prefix(reply) if manual_changed else reply
        if suffix == ".xlsx":
            reply = await self._edit_latest_excel(path, instruction, channel, save_copy=save_copy)
            return _manual_edit_safety_prefix(reply) if manual_changed else reply
        if suffix != ".docx":
            return "I can edit the latest Word, Excel, or PowerPoint file first. Tell me which file to use."
        if action_permission("edit_document") != "allow":
            return "I need your confirmation before editing that document."
        session = await active_artifact_session(self.db_path, channel, str(path))
        if simple_docx_edit_instruction(instruction):
            reply = await self._simple_word_edit(path, instruction, channel, save_copy=save_copy, session=session)
            return _manual_edit_safety_prefix(reply) if manual_changed else reply
        try:
            current = await asyncio.to_thread(extract_docx_text, path)
            topic = _session_edit_topic(session, "docx", instruction) if session else _edited_word_topic(path, instruction, current)
            preflight = await self._artifact_preflight("docx", topic)
            doc_kind = getattr(preflight, "doc_kind", "generic_document")
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
        quality = await self._word_quality(target, topic, attempt_number=1, doc_kind=doc_kind)
        attempts = 1
        max_attempts = artifact_qa_max_attempts("docx")
        while not quality.passed and attempts < max_attempts:
            attempts += 1
            repaired = await self._repair_word_doc(target, topic, quality, attempts)
            if not repaired:
                break
            quality = await self._word_quality(target, topic, attempt_number=attempts, doc_kind=doc_kind)
        if not quality.passed:
            if (channel == "imac" or _draft_override_requested(instruction)) and not _word_quality_hard_blocks(quality):
                await upsert_preference(self.db_path, LAST_DOC_KEY, str(target), source="document")
                return await self._draft_with_issues(
                    "edited Word draft",
                    target,
                    channel,
                    "Microsoft Word",
                    quality.short_issue_text(),
                    attempts=attempts,
                    topic=topic,
                )
            await _preserve_failed_word_draft(self.db_path, target)
            if save_copy and target.exists():
                await asyncio.to_thread(target.unlink)
            elif backup:
                await asyncio.to_thread(shutil.copy2, backup, path)
            if "Word edit restore" not in self.last_model_lane:
                self.last_model_lane += " + Word edit restore"
            await upsert_preference(self.db_path, LAST_DOC_KEY, str(path), source="document")
            return f"I tried to update the latest Word document, but QA failed: {quality.short_issue_text()}. I kept the original unchanged."
        await self._remember(target, f"Edited Word draft: {quality.summary}", False, channel, "docx", topic)
        if session:
            await update_artifact_session_after_edit(self.db_path, session, channel, target, instruction)
        if not quality.passed:
            return await self._draft_with_issues("edited Word draft", target, channel, "Microsoft Word", quality.short_issue_text(), topic=topic)
        label = "edited Word copy" if save_copy else "updated Word document"
        reply = await self._done(label, target, channel, "Microsoft Word")
        if not save_copy and backup:
            prefix = "Done. I updated the latest Word document in place. I kept an internal backup before editing."
            if channel == "telegram":
                return _attach(prefix, target, channel)
            return prefix if "asked Microsoft Word to open it on the iMac" not in reply else f"{prefix} I asked Microsoft Word to open it on the iMac."
        return _manual_edit_safety_prefix(reply) if manual_changed else reply

    async def _simple_word_edit(self, path: Path, instruction: str, channel: str, *, save_copy: bool = False, session=None) -> str:
        current = await asyncio.to_thread(extract_docx_text, path)
        topic = _session_edit_topic(session, "docx", instruction) if session else _edited_word_topic(path, instruction, current)
        preflight = await self._artifact_preflight("docx", topic)
        doc_kind = getattr(preflight, "doc_kind", "generic_document")
        self.last_model_lane = f"{preflight.lane_prefix} + local Word edit"
        self.last_cost_recorded = preflight.cost_recorded
        target = versioned_path(path) if save_copy else path
        backup = await asyncio.to_thread(_backup_word_file, path)
        if save_copy:
            await asyncio.to_thread(shutil.copy2, path, target)
        await asyncio.to_thread(apply_simple_docx_edit, target, instruction)
        quality = await self._word_quality(target, topic, attempt_number=1, doc_kind=doc_kind)
        if not quality.passed:
            if (channel == "imac" or _draft_override_requested(instruction)) and not _word_quality_hard_blocks(quality):
                await upsert_preference(self.db_path, LAST_DOC_KEY, str(target), source="document")
                return await self._draft_with_issues(
                    "edited Word draft",
                    target,
                    channel,
                    "Microsoft Word",
                    quality.short_issue_text(),
                    topic=topic,
                )
            await _preserve_failed_word_draft(self.db_path, target)
            if save_copy and target.exists():
                await asyncio.to_thread(target.unlink)
            elif backup:
                await asyncio.to_thread(shutil.copy2, backup, path)
            if "Word edit restore" not in self.last_model_lane:
                self.last_model_lane += " + Word edit restore"
            await upsert_preference(self.db_path, LAST_DOC_KEY, str(path), source="document")
            return f"I tried to update the latest Word document, but QA failed: {quality.short_issue_text()}. I kept the original unchanged."
        await self._remember(target, f"Edited Word draft: {quality.summary}", False, channel, "docx", topic)
        if session:
            await update_artifact_session_after_edit(self.db_path, session, channel, target, instruction)
        if save_copy:
            return await self._done("edited Word copy", target, channel, "Microsoft Word")
        return _attach("Done. I updated the latest Word document in place. I kept an internal backup before editing.", target, channel)


def _manual_edit_safety_prefix(reply: str) -> str:
    prefix = "I noticed the file changed, so I made a new version instead of overwriting your edits."
    if not reply:
        return prefix
    return f"{prefix} {reply}"


def _session_edit_topic(session, artifact_type: str, instruction: str) -> str:
    state = apply_artifact_edit_delta(session.state, instruction)
    topic = topic_from_state(artifact_type, state, fallback=session.topic)
    if artifact_type == "docx" and re.search(r"\b(?:putty|ssh|serial|console|cli|command|config)\b", instruction, re.I):
        if re.search(r"\brouter\b", f"{topic} {session.topic} {instruction}", re.I):
            return "Router Setup Guide With PuTTY Config"
        return f"{topic} With PuTTY Config"
    day_match = re.search(r"\b(\d{1,2})\s*[- ]?\s*(?:day|days)\b", instruction, re.I)
    if artifact_type == "docx" and day_match:
        days = int(day_match.group(1))
        base_source = session.topic or topic
        base = re.sub(r"\b\d{1,2}\s+days?\b", " ", base_source, flags=re.I)
        base = re.sub(r"^\d{1,2}\s*[- ]?\s*day\s+", " ", base, flags=re.I)
        base = " ".join(base.split()) or session.topic
        return f"{days}-day {base}"
    return topic
