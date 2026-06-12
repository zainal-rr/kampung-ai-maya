from __future__ import annotations

from document_actions_context import *
from artifact_retry_policy import artifact_qa_max_attempts
from document_actions_content_helpers import (
    _attach,
    _budget_filename_topic,
    _budget_rows,
    _budget_title,
    _budget_topic,
    _excel_lane,
    _internal_excel_topic,
    _prefixed_lane,
    _retired_kampung_ai_cost_topic,
    _saas_tracker_rows,
    _saas_tracker_topic,
    _task_tracker_rows,
    _task_tracker_topic,
    _travel_budget_topic,
)
from document_actions_office_sessions import _office_session_edit_topic
from excel_species import detect_excel_species
from excel_species_draft import excel_species_prompt_context
from office_edit_helpers import (
    apply_simple_xlsx_edit,
    backup_office_file,
    edited_office_topic,
    simple_xlsx_edit_instruction,
    xlsx_edit_request,
    xlsx_snapshot,
)


class DocumentExcelMixin:
    async def _edit_latest_excel(self, path: Path, instruction: str, channel: str, *, save_copy: bool = False) -> str:
        if action_permission("edit_document") != "allow":
            return "I need your confirmation before editing that workbook."
        session = await active_artifact_session(self.db_path, channel, str(path))
        if simple_xlsx_edit_instruction(instruction):
            return await self._edit_latest_excel_simple(path, instruction, channel, session, save_copy)
        try:
            current = await asyncio.to_thread(xlsx_snapshot, path)
            topic = _office_session_edit_topic(session, "xlsx", instruction) if session else edited_office_topic(path, instruction, current)
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
        headers, rows = _budget_rows(f"{topic} {instruction}") if _budget_topic(f"{topic} {instruction}") else spreadsheet_from_markdown(topic, draft.content)
        headers, rows = await style_table(self.db_path, headers, rows)
        await asyncio.to_thread(create_xlsx, target, topic.title(), headers, rows)
        return await self._finish_excel_edit(path, target, backup, topic, instruction, channel, session, save_copy)

    async def _edit_latest_excel_simple(self, path: Path, instruction: str, channel: str, session, save_copy: bool) -> str:
        current = await asyncio.to_thread(xlsx_snapshot, path)
        topic = _office_session_edit_topic(session, "xlsx", instruction) if session else edited_office_topic(path, instruction, current)
        preflight = await self._artifact_preflight("xlsx", topic)
        self.last_model_lane = _prefixed_lane("local Excel edit", preflight)
        self.last_cost_recorded = bool(preflight and preflight.cost_recorded)
        target = versioned_path(path) if save_copy else path
        backup = await asyncio.to_thread(backup_office_file, path)
        if save_copy:
            await asyncio.to_thread(shutil.copy2, path, target)
        await asyncio.to_thread(apply_simple_xlsx_edit, target, instruction)
        return await self._finish_excel_edit(path, target, backup, topic, instruction, channel, session, save_copy)

    async def _finish_excel_edit(self, original: Path, target: Path, backup: Path | None, topic: str, instruction: str, channel: str, session, save_copy: bool) -> str:
        quality = await self._excel_quality(target, topic)
        if not quality.passed:
            await self._restore_failed_edit(original, target, backup, save_copy)
            self.last_model_lane += " + Excel edit restore"
            return f"I tried to update the latest Excel workbook, but QA failed: {quality.short_issue_text()}. I kept the original unchanged."
        await self._remember(target, f"Edited Excel workbook: {quality.summary}", False, channel, "xlsx", topic)
        if session:
            await update_artifact_session_after_edit(self.db_path, session, channel, target, instruction)
        if save_copy:
            return await self._done("edited Excel copy", target, channel, "Microsoft Excel")
        return _attach("Done. I updated the latest Excel workbook in place. I kept an internal backup before editing.", target, channel)

    async def _create_excel(self, topic: str, project_scoped: bool, channel: str) -> str:
        if _retired_kampung_ai_cost_topic(topic):
            self.last_model_lane = "Telegram /cost usage estimate"
            self.last_cost_recorded = False
            return "I don't create a separate Kampung AI cost workbook anymore. Use /cost for the live usage estimate. If you need a file later, ask me to export /cost."
        preflight = None if _internal_excel_topic(topic) else await self._artifact_preflight("xlsx", topic)
        self.last_model_lane = _prefixed_lane(_excel_lane(topic), preflight)
        self.last_cost_recorded = bool(preflight and preflight.cost_recorded)
        path = await self._path("xlsx", topic, project_scoped)
        if not path_allowed(path):
            return f"I can't write to {path}."
        if _saas_tracker_topic(topic):
            return await self._create_saas_tracker(path, topic, project_scoped, channel)
        if is_kampung_ai_testing_comparison(topic):
            return await self._create_testing_comparison(path, topic, project_scoped, channel)
        if _task_tracker_topic(topic):
            return await self._create_task_tracker(path, topic, project_scoped, channel, preflight)
        if _budget_topic(topic):
            return await self._create_budget_workbook(topic, project_scoped, channel, preflight)
        return await self._create_species_or_generic_workbook(path, topic, project_scoped, channel, preflight)

    async def _create_saas_tracker(self, path: Path, topic: str, project_scoped: bool, channel: str) -> str:
        headers, rows = _saas_tracker_rows(topic)
        headers, rows = await style_table(self.db_path, headers, rows)
        await asyncio.to_thread(create_xlsx, path, "SaaS Cost Tracker", headers, rows)
        return await self._finish_excel(path, "Excel SaaS cost tracker", topic, project_scoped, channel)

    async def _create_testing_comparison(self, path: Path, topic: str, project_scoped: bool, channel: str) -> str:
        headers, rows = kampung_ai_testing_rows()
        headers, rows = await style_table(self.db_path, headers, rows)
        await asyncio.to_thread(create_xlsx, path, "Kampung AI Testing Comparison", headers, rows)
        return await self._finish_excel(path, "Excel testing comparison", topic, project_scoped, channel)

    async def _create_task_tracker(self, path: Path, topic: str, project_scoped: bool, channel: str, preflight) -> str:
        self.last_model_lane = _prefixed_lane("Local office task tracker workbook", preflight)
        headers, rows = _task_tracker_rows(topic)
        headers, rows = await style_table(self.db_path, headers, rows)
        await asyncio.to_thread(create_xlsx, path, "Office Task Tracker", headers, rows)
        return await self._finish_excel(path, "Excel task tracker", topic, project_scoped, channel)

    async def _create_budget_workbook(self, topic: str, project_scoped: bool, channel: str, preflight) -> str:
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

        async def rebuild_budget(attempt: int, quality: ArtifactQualityResult) -> None:
            fresh_headers, fresh_rows = _budget_rows(f"{topic} {quality.short_issue_text()}")
            fresh_headers, fresh_rows = await style_table(self.db_path, fresh_headers, fresh_rows)
            await asyncio.to_thread(create_xlsx, path, _budget_title(topic), fresh_headers, fresh_rows)

        return await self._finish_excel(path, "Excel budget tracker", topic, project_scoped, channel, rebuild=rebuild_budget)

    async def _create_species_or_generic_workbook(self, path: Path, topic: str, project_scoped: bool, channel: str, preflight) -> str:
        species = detect_excel_species(topic)
        species_contract = excel_species_prompt_context(species, topic) if species else ""
        try:
            draft = await self._draft_markdown(topic, preflight, extra_context=species_contract)
        except Exception as exc:
            return document_generation_failed("Excel spreadsheet", exc)
        if not draft:
            return document_generation_failed("Excel spreadsheet", RuntimeError("Gemini returned no spreadsheet content."))
        self.last_model_lane = _prefixed_lane(
            "Gemini Flash grounded role-based spreadsheet draft" if draft.grounded else "Gemini Flash role-based spreadsheet draft",
            preflight,
        )
        self.last_cost_recorded = True
        headers, rows = spreadsheet_from_markdown(topic, draft.content)
        headers, rows = await style_table(self.db_path, headers, rows)
        await asyncio.to_thread(create_xlsx, path, topic.title(), headers, rows)
        return await self._finish_excel(path, "Excel draft", topic, project_scoped, channel, rebuild=self._generic_excel_rebuilder(path, topic, preflight, species_contract))

    def _generic_excel_rebuilder(self, path: Path, topic: str, preflight, species_contract: str):
        async def rebuild_generic(attempt: int, quality: ArtifactQualityResult) -> None:
            repair_topic = (
                "Repair this Excel workbook draft. Return corrected Markdown table content only.\n"
                f"Original request: {topic}\n"
                f"QA issues to fix: {quality.short_issue_text()}\n"
                "The workbook must have useful headers, populated rows, and formulas when the request implies totals, budgets, costs, or tracking."
            )
            repaired = await self._draft_markdown(repair_topic, preflight, extra_context=species_contract)
            if not repaired:
                return
            fresh_headers, fresh_rows = spreadsheet_from_markdown(topic, repaired.content)
            fresh_headers, fresh_rows = await style_table(self.db_path, fresh_headers, fresh_rows)
            await asyncio.to_thread(create_xlsx, path, topic.title(), fresh_headers, fresh_rows)

        return rebuild_generic

    async def _finish_excel(self, path: Path, label: str, topic: str, project_scoped: bool, channel: str, rebuild=None) -> str:
        quality = await self._excel_quality(path, topic)
        attempts = 1
        max_attempts = artifact_qa_max_attempts("xlsx")
        while not quality.passed and rebuild and attempts < max_attempts:
            attempts += 1
            result = rebuild(attempts, quality)
            if asyncio.iscoroutine(result):
                await result
            if "Excel repair pass" not in self.last_model_lane:
                self.last_model_lane += " + Excel repair pass"
            quality = await self._excel_quality(path, topic)
        if not quality.passed:
            return await self._draft_with_issues(label, path, channel, "Microsoft Excel", quality.short_issue_text())
        await self._remember(path, f"Created {label}: {quality.summary}", project_scoped, channel, "xlsx", topic)
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
