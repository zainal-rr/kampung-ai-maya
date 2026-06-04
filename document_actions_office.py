from __future__ import annotations

from document_actions_context import *
from document_actions_content_helpers import (
    _attach,
    _budget_filename_topic,
    _budget_rows,
    _budget_title,
    _budget_topic,
    _excel_lane,
    _internal_excel_topic,
    _kampung_ai_cost_topic,
    _prefixed_lane,
    _quick_request,
    _strip_quality_words,
    _task_tracker_rows,
    _task_tracker_topic,
    _travel_budget_topic,
)
from office_edit_helpers import (
    apply_simple_xlsx_edit,
    backup_office_file,
    edited_office_topic,
    pptx_edit_request,
    pptx_outline,
    simple_xlsx_edit_instruction,
    xlsx_edit_request,
    xlsx_snapshot,
)


class DocumentOfficeMixin:
    async def _edit_latest_powerpoint(self, path: Path, instruction: str, channel: str, *, save_copy: bool = False) -> str:
        if action_permission("edit_presentation") != "allow":
            return "I need your confirmation before editing that presentation."
        try:
            current = await asyncio.to_thread(pptx_outline, path)
            topic = edited_office_topic(path, instruction, current)
            preflight = await self._artifact_preflight("pptx", topic)
            self.last_model_lane = f"{preflight.lane_prefix} + Gemini Flash PowerPoint edit"
            self.last_cost_recorded = preflight.cost_recorded
            draft = await self._draft_markdown(pptx_edit_request(topic, instruction, current), preflight)
        except Exception as exc:
            return document_generation_failed("PowerPoint edit", exc)
        if not draft:
            return document_generation_failed("PowerPoint edit", RuntimeError("Gemini returned no edited deck content."))
        target = versioned_path(path) if save_copy else path
        backup = await asyncio.to_thread(backup_office_file, path)
        slides = await style_sections(self.db_path, slides_from_markdown(draft.content, topic))
        reviewed = await review_presentation_slides(self.db_path, topic, slides)
        if reviewed != slides:
            self.last_model_lane += " + Claude presentation design review"
            slides = reviewed
        qa = await create_powerpoint_with_qa(self.db_path, target, topic.title(), slides, DIRECT_DOC_RUN_ID, LAST_DOC_KEY)
        if not qa.passed:
            await self._restore_failed_edit(path, target, backup, save_copy)
            self.last_model_lane += " + PowerPoint edit restore"
            return f"I tried to update the latest PowerPoint, but QA failed: {qa.summary()} I kept the original unchanged."
        await self._remember(target, f"Edited PowerPoint draft: {qa.summary()}", False)
        if save_copy:
            return await self._done_powerpoint("edited PowerPoint copy", target, channel)
        return _attach("Done. I updated the latest PowerPoint in place. I kept an internal backup before editing.", target, channel)

    async def _edit_latest_excel(self, path: Path, instruction: str, channel: str, *, save_copy: bool = False) -> str:
        if action_permission("edit_document") != "allow":
            return "I need your confirmation before editing that workbook."
        if simple_xlsx_edit_instruction(instruction):
            current = await asyncio.to_thread(xlsx_snapshot, path)
            topic = edited_office_topic(path, instruction, current)
            preflight = await self._artifact_preflight("xlsx", topic)
            self.last_model_lane = _prefixed_lane("local Excel edit", preflight)
            self.last_cost_recorded = bool(preflight and preflight.cost_recorded)
            target = versioned_path(path) if save_copy else path
            backup = await asyncio.to_thread(backup_office_file, path)
            if save_copy:
                await asyncio.to_thread(shutil.copy2, path, target)
            await asyncio.to_thread(apply_simple_xlsx_edit, target, instruction)
            quality = await self._excel_quality(target, topic)
            if not quality.passed:
                await self._restore_failed_edit(path, target, backup, save_copy)
                self.last_model_lane += " + Excel edit restore"
                return f"I tried to update the latest Excel workbook, but QA failed: {quality.short_issue_text()}. I kept the original unchanged."
            await self._remember(target, f"Edited Excel workbook: {quality.summary}", False)
            if save_copy:
                return await self._done("edited Excel copy", target, channel, "Microsoft Excel")
            return _attach("Done. I updated the latest Excel workbook in place. I kept an internal backup before editing.", target, channel)
        try:
            current = await asyncio.to_thread(xlsx_snapshot, path)
            topic = edited_office_topic(path, instruction, current)
            preflight = await self._artifact_preflight("xlsx", topic)
            self.last_model_lane = f"{preflight.lane_prefix} + Gemini Flash Excel edit"
            self.last_cost_recorded = preflight.cost_recorded
            draft = await self._draft_markdown(xlsx_edit_request(topic, instruction, current), preflight)
        except Exception as exc:
            return document_generation_failed("Excel edit", exc)
        if not draft:
            return document_generation_failed("Excel edit", RuntimeError("Gemini returned no edited workbook content."))
        target = versioned_path(path) if save_copy else path
        backup = await asyncio.to_thread(backup_office_file, path)
        if _budget_topic(f"{topic} {instruction}"):
            headers, rows = _budget_rows(f"{topic} {instruction}")
        else:
            headers, rows = spreadsheet_from_markdown(topic, draft.content)
        headers, rows = await style_table(self.db_path, headers, rows)
        await asyncio.to_thread(create_xlsx, target, topic.title(), headers, rows)
        quality = await self._excel_quality(target, topic)
        if not quality.passed:
            await self._restore_failed_edit(path, target, backup, save_copy)
            self.last_model_lane += " + Excel edit restore"
            return f"I tried to update the latest Excel workbook, but QA failed: {quality.short_issue_text()}. I kept the original unchanged."
        await self._remember(target, f"Edited Excel workbook: {quality.summary}", False)
        if save_copy:
            return await self._done("edited Excel copy", target, channel, "Microsoft Excel")
        return _attach("Done. I updated the latest Excel workbook in place. I kept an internal backup before editing.", target, channel)

    async def _restore_failed_edit(self, original: Path, target: Path, backup: Path | None, save_copy: bool) -> None:
        if save_copy and target.exists():
            await asyncio.to_thread(target.unlink)
        elif backup:
            await asyncio.to_thread(shutil.copy2, backup, original)
        await upsert_preference(self.db_path, LAST_DOC_KEY, str(original), source="document")

    async def _create_powerpoint(self, topic: str, channel: str) -> str:
        quick = _quick_request(topic)
        topic = _strip_quality_words(topic)
        preflight = await self._artifact_preflight("pptx", topic)
        pptx_taste_lane = f"{preflight.lane_prefix} + PowerPoint design taste"
        self.last_model_lane = f"{pptx_taste_lane} + Gemini Flash role-based presentation content"
        self.last_cost_recorded = preflight.cost_recorded
        path = named_artifact_path(self.workspace / "presentations", topic, "pptx")
        if not path_allowed(path):
            return f"I can't write to {path}."
        try:
            draft = await self._draft_markdown(topic, preflight)
        except Exception as exc:
            return document_generation_failed("PowerPoint", exc)
        if not draft:
            return document_generation_failed("PowerPoint", RuntimeError("Gemini returned no presentation content."))
        self.last_model_lane = (
            f"{pptx_taste_lane} + Gemini Flash grounded role-based presentation content"
            if draft.grounded else f"{pptx_taste_lane} + Gemini Flash role-based presentation content"
        )
        self.last_cost_recorded = True
        slides = await style_sections(self.db_path, slides_from_markdown(draft.content, topic))
        reviewed = await review_presentation_slides(self.db_path, topic, slides)
        if reviewed != slides:
            self.last_model_lane += " + Claude presentation design review"
            slides = reviewed
        slides = await style_sections(self.db_path, slides)
        qa = await create_powerpoint_with_qa(
            self.db_path,
            path,
            topic.title(),
            slides,
            DIRECT_DOC_RUN_ID,
            LAST_DOC_KEY,
            auto_improve=not quick,
        )
        if qa.revisions:
            self.last_model_lane += " + topic-safe polish pass"
        if not qa.passed:
            return await self._attach_powerpoint(
                f"I created a PowerPoint draft, but {qa.summary()} I’m not calling it final.",
                path,
                channel,
                include_deck=False,
            )
        label = "starter PowerPoint draft" if quick else "PowerPoint draft"
        return await self._done_powerpoint(f"{label}. {qa.summary()}", path, channel)

    async def _done_powerpoint(self, label: str, path: Path, channel: str) -> str:
        await self._remember(path, f"Created {label}", False)
        if channel == "telegram":
            return await self._attach_powerpoint(f"Done. I created a {label}.", path, channel)
        await asyncio.to_thread(open_created_file, path, self.bridge, "Microsoft PowerPoint")
        return f"Done. I created a {label} and opened it on the iMac."

    async def _attach_powerpoint(self, message: str, path: Path, channel: str, *, include_deck: bool = True) -> str:
        if channel != "telegram":
            return message
        markers = []
        if include_deck:
            markers.append(f"[file:{path}]")
        return f"{message}\n" + "\n".join(markers) if markers else message

    async def _create_excel(self, topic: str, project_scoped: bool, channel: str) -> str:
        preflight = None if _internal_excel_topic(topic) else await self._artifact_preflight("xlsx", topic)
        self.last_model_lane = _prefixed_lane(_excel_lane(topic), preflight)
        self.last_cost_recorded = bool(preflight and preflight.cost_recorded)
        path = await self._path("xlsx", topic, project_scoped)
        if not path_allowed(path):
            return f"I can't write to {path}."
        if _kampung_ai_cost_topic(topic):
            headers, rows = await kampung_ai_cost_rows(self.db_path)
            headers, rows = await style_table(self.db_path, headers, rows)
            await asyncio.to_thread(create_xlsx, path, "Kampung AI Cost Tracker", headers, rows)
            return await self._finish_excel(path, "Kampung AI cost tracker", topic, project_scoped, channel)
        if is_kampung_ai_testing_comparison(topic):
            headers, rows = kampung_ai_testing_rows()
            headers, rows = await style_table(self.db_path, headers, rows)
            await asyncio.to_thread(create_xlsx, path, "Kampung AI Testing Comparison", headers, rows)
            return await self._finish_excel(path, "Excel testing comparison", topic, project_scoped, channel)
        if _task_tracker_topic(topic):
            self.last_model_lane = _prefixed_lane("Local office task tracker workbook", preflight)
            headers, rows = _task_tracker_rows(topic)
            headers, rows = await style_table(self.db_path, headers, rows)
            await asyncio.to_thread(create_xlsx, path, "Office Task Tracker", headers, rows)
            return await self._finish_excel(path, "Excel task tracker", topic, project_scoped, channel)
        if _budget_topic(topic):
            if _travel_budget_topic(topic):
                from travel_budget import create_travel_budget_excel

                self.last_model_lane = _prefixed_lane("Gemini Flash role-based travel budget notes + Local travel budget workbook", preflight)
                self.last_cost_recorded = True
                reply = await create_travel_budget_excel(self.db_path, topic, self.bridge, channel, preflight.content if preflight else "")
                self.last_model_lane += " + local Excel QA"
                self.last_model_lane += " + Claude Excel review" if os.getenv("ANTHROPIC_API_KEY") else " + Claude Excel review skipped"
                return reply
            self.last_model_lane = _prefixed_lane("Local editable budget workbook", preflight)
            self.last_cost_recorded = bool(preflight and preflight.cost_recorded)
            path = await self._path("xlsx", _budget_filename_topic(topic), project_scoped)
            headers, rows = _budget_rows(topic)
            headers, rows = await style_table(self.db_path, headers, rows)
            await asyncio.to_thread(create_xlsx, path, _budget_title(topic), headers, rows)
            return await self._finish_excel(path, "Excel budget tracker", topic, project_scoped, channel)
        try:
            draft = await self._draft_markdown(topic, preflight)
        except Exception as exc:
            return document_generation_failed("Excel spreadsheet", exc)
        if not draft:
            return document_generation_failed("Excel spreadsheet", RuntimeError("Gemini returned no spreadsheet content."))
        self.last_model_lane = (
            _prefixed_lane("Gemini Flash grounded role-based spreadsheet draft", preflight)
            if draft.grounded else _prefixed_lane("Gemini Flash role-based spreadsheet draft", preflight)
        )
        self.last_cost_recorded = True
        headers, rows = spreadsheet_from_markdown(topic, draft.content)
        headers, rows = await style_table(self.db_path, headers, rows)
        await asyncio.to_thread(create_xlsx, path, topic.title(), headers, rows)
        return await self._finish_excel(path, "Excel draft", topic, project_scoped, channel)

    async def _finish_excel(self, path: Path, label: str, topic: str, project_scoped: bool, channel: str) -> str:
        quality = await self._excel_quality(path, topic)
        await self._remember(path, f"Created {label}: {quality.summary}", project_scoped)
        if not quality.passed:
            return await self._draft_with_issues(label, path, channel, "Microsoft Excel", quality.short_issue_text())
        return await self._done(label, path, channel, "Microsoft Excel")

    async def _excel_quality(self, path: Path, topic: str) -> ArtifactQualityResult:
        local_qa = await asyncio.to_thread(validate_xlsx_path, path, topic)
        if "local Excel QA" not in self.last_model_lane:
            self.last_model_lane += " + local Excel QA"
        review_qa = await review_artifact_quality(self.db_path, "xlsx", topic, await asyncio.to_thread(extract_xlsx_text, path))
        if review_qa.review_model and "Claude Excel review" not in self.last_model_lane:
            self.last_model_lane += " + Claude Excel review"
        elif review_qa.warnings and "Claude Excel review" not in self.last_model_lane:
            self.last_model_lane += " + Claude Excel review skipped"
        return local_qa.merge(review_qa)
