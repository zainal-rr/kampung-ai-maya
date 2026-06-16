"""Office artifact mixin for Excel and PowerPoint creation/editing.

`DocumentActionRouter` owns intent resolution, while this mixin owns the
Office-specific work: editing the latest workbook/deck, preserving backups,
calling the local workbook/deck builders, and routing results through artifact
QA/delivery. Word has its own mixin because Word editing and visual QA have
different rules.

The important continuity behavior lives here with `artifact_sessions`: follow-up
edits should modify the current artifact in place unless the user explicitly
asks for a copy or new version.
"""

from __future__ import annotations

from maya_documents.document_actions_context import *
from maya_core.created_file_summary import created_file_content_summary
from maya_documents.deck_species import deck_species_prompt_context, detect_deck_species
from maya_documents.document_actions_content_helpers import _attach, _quick_request, _strip_quality_words
from maya_documents.document_actions_excel_mixin import DocumentExcelMixin
from maya_documents.document_actions_office_sessions import _office_session_edit_topic
from maya_voice.work_runtime import set_current_voice_work_phase
from maya_documents.delivery_policy import pptx_quality_hard_block
from maya_documents.office_edit_helpers import (
    backup_office_file,
    edited_office_topic,
    pptx_edit_request,
    pptx_outline,
)


class DocumentOfficeMixin(DocumentExcelMixin):
    async def _edit_latest_powerpoint(self, path: Path, instruction: str, channel: str, *, save_copy: bool = False) -> str:
        if action_permission("edit_presentation") != "allow":
            return "I need your confirmation before editing that presentation."
        try:
            current = await asyncio.to_thread(pptx_outline, path)
            session = await active_artifact_session(self.db_path, channel, str(path))
            topic = _office_session_edit_topic(session, "pptx", instruction) if session else edited_office_topic(path, instruction, current)
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
            if channel == "imac" and not pptx_quality_hard_block(qa):
                await self._remember(target, f"Edited PowerPoint draft: {qa.summary()}", False, channel, "pptx", topic)
                if session:
                    await update_artifact_session_after_edit(self.db_path, session, channel, target, instruction)
                return await self._attach_powerpoint(
                    f"I updated the PowerPoint draft, but {qa.summary()} I’m not calling it final.",
                    target,
                    channel,
                    include_deck=True,
                )
            await self._restore_failed_edit(path, target, backup, save_copy)
            self.last_model_lane += " + PowerPoint edit restore"
            return f"I tried to update the latest PowerPoint, but QA failed: {qa.summary()} I kept the original unchanged."
        await self._remember(target, f"Edited PowerPoint draft: {qa.summary()}", False, channel, "pptx", topic)
        if session:
            await update_artifact_session_after_edit(self.db_path, session, channel, target, instruction)
        if save_copy:
            return await self._done_powerpoint("edited PowerPoint copy", target, channel)
        return _attach("Done. I updated the latest PowerPoint in place. I kept an internal backup before editing.", target, channel)

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
        # Deck honesty contract: review/pitch species must use fill-in slots
        # instead of fabricating sprint data or traction (live 2026-06-11).
        deck_contract = deck_species_prompt_context(detect_deck_species(topic))
        try:
            draft = await self._draft_markdown(topic, preflight, extra_context=deck_contract)
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
            visual_image_max=None,
        )
        if qa.revisions:
            self.last_model_lane += " + topic-safe polish pass"
        if not qa.passed:
            return await self._attach_powerpoint(
                f"I created a PowerPoint draft, but {qa.summary()} I’m not calling it final.",
                path,
                channel,
                include_deck=True,
            )
        label = "starter PowerPoint draft" if quick else "PowerPoint draft"
        return await self._done_powerpoint(f"{label}. {qa.summary()}", path, channel, topic)

    async def _done_powerpoint(self, label: str, path: Path, channel: str, topic: str = "") -> str:
        await self._remember(path, f"Created {label}", False, channel, "pptx", topic)
        if channel == "telegram":
            return await self._attach_powerpoint(f"Done. I created a {label}.", path, channel)
        summary = await asyncio.to_thread(created_file_content_summary, path)
        if not await set_current_voice_work_phase("opening", f"opening {path.name}"):
            return f"I cancelled that PowerPoint before opening it. It is saved in the Maya documents folder as {path.name}."
        try:
            opened_app = await asyncio.to_thread(open_created_file, path, self.bridge, "Microsoft PowerPoint")
        except Exception as exc:
            return f"Done. I created a {label} at {path}. I saved it here: {path}. I could not open it: {exc}. {summary}"
        opened = opened_app or "Microsoft PowerPoint"
        return f"Done. I created a {label} at {path}. I asked {opened} to open it on the iMac. {summary}"

    async def _attach_powerpoint(self, message: str, path: Path, channel: str, *, include_deck: bool = True) -> str:
        if channel != "telegram":
            if not include_deck:
                return f"{message} Draft saved at {path}."
            summary = await asyncio.to_thread(created_file_content_summary, path)
            if not await set_current_voice_work_phase("opening", f"opening {path.name}"):
                return f"I cancelled that PowerPoint draft before opening it. It is saved in the Maya documents folder as {path.name}."
            try:
                opened_app = await asyncio.to_thread(open_created_file, path, self.bridge, "Microsoft PowerPoint")
            except Exception as exc:
                return f"{message} Draft saved at {path}. I could not open it: {exc}. {summary}"
            opened = opened_app or "Microsoft PowerPoint"
            return f"{message} Draft saved at {path}. I asked {opened} to open it on the iMac. {summary}"
        markers = []
        if include_deck:
            markers.append(f"[file:{path}]")
        return f"{message}\n" + "\n".join(markers) if markers else message
