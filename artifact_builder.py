"""Shared finalization path for user-facing Office artifacts.

This module sits after the type-specific builders (`document_actions_word`,
`travel_budget`, and PowerPoint flows) and before channel delivery. Its job is
to turn an already-created local file into a durable Maya artifact: validate it,
run model review when available, retry through the caller-supplied rebuild hook,
record latest-document/session metadata, and deliver through iMac or Telegram.

Keep this module type-agnostic. Word, Excel, and PowerPoint decide how to build
or repair their files before calling this layer; this layer decides whether the
finished file is safe to call final and whether it should be attached/opened.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from artifact_retry_policy import artifact_qa_max_attempts, qa_retry_exhausted_message
from artifact_sessions import record_artifact_session
from created_file_summary import created_file_content_summary
from artifact_quality import (
    ArtifactQualityResult,
    extract_docx_text,
    extract_xlsx_text,
    review_artifact_quality,
    resolve_quality_disagreement,
    validate_docx_path,
    validate_xlsx_path,
)
from created_file_opener import open_created_file
from harness_artifact_store import record_structured_artifact
from harness_models import local_artifact
from maya_voice.work_runtime import set_current_voice_work_phase
from maya_documents.delivery_policy import docx_quality_hard_block, excel_quality_hard_block
from storage import upsert_preference
from utils import OSBridge


LAST_DOC_KEY = "maya_last_document_path"
LAST_DRAFT_DOC_KEY = "maya_last_draft_document_path"


@dataclass(frozen=True)
class BuiltArtifact:
    path: Path
    quality: ArtifactQualityResult
    reply: str


class ArtifactBuilder:
    def __init__(self, db_path: str, bridge: OSBridge | None = None, last_doc_key: str = LAST_DOC_KEY):
        self.db_path = db_path
        self.bridge = bridge or OSBridge()
        self.last_doc_key = last_doc_key

    async def finish_docx(
        self,
        path: Path,
        topic: str,
        channel: str,
        *,
        run_id: str,
        source_tool: str,
        app_name: str | None = "Microsoft Word",
        success_message: str | None = None,
        draft_message: str | None = None,
        open_file: bool | None = None,
        doc_kind: str = "generic_document",
        rebuild=None,
    ) -> BuiltArtifact:
        quality = await self._docx_quality(path, topic, attempt_number=1, doc_kind=doc_kind)
        attempts = 1
        while not quality.passed and rebuild and attempts < artifact_qa_max_attempts("docx"):
            attempts += 1
            await _run_rebuild(rebuild, attempts, quality)
            quality = await self._docx_quality(path, topic, attempt_number=attempts, doc_kind=doc_kind)
            quality.repair_attempted = True
        return await self._finish(
            path,
            topic,
            quality,
            channel,
            run_id,
            source_tool,
            app_name,
            success_message,
            draft_message,
            open_file,
            attempts_run=attempts,
            repair_available=bool(rebuild),
        )

    async def finish_xlsx(
        self,
        path: Path,
        topic: str,
        channel: str,
        *,
        run_id: str,
        source_tool: str,
        label: str,
        app_name: str | None = "Microsoft Excel",
        open_file: bool | None = None,
        rebuild=None,
    ) -> BuiltArtifact:
        quality = await self._xlsx_quality(path, topic, attempt_number=1)
        attempts = 1
        while not quality.passed and rebuild and attempts < artifact_qa_max_attempts("xlsx"):
            attempts += 1
            await _run_rebuild(rebuild, attempts, quality)
            quality = await self._xlsx_quality(path, topic, attempt_number=attempts)
            quality.repair_attempted = True
        success = f"Done. I created {label}."
        draft = f"I created {label}, but QA found: {quality.short_issue_text()}. I’m keeping it as a draft."
        return await self._finish(
            path,
            topic,
            quality,
            channel,
            run_id,
            source_tool,
            app_name,
            success,
            draft,
            open_file,
            attempts_run=attempts,
            repair_available=bool(rebuild),
        )

    async def _docx_quality(
        self,
        path: Path,
        topic: str,
        *,
        attempt_number: int = 1,
        doc_kind: str = "generic_document",
    ) -> ArtifactQualityResult:
        local_qa = await asyncio.to_thread(validate_docx_path, path, topic, doc_kind=doc_kind)
        extracted = await asyncio.to_thread(extract_docx_text, path)
        review_qa = await review_artifact_quality(
            self.db_path,
            "docx",
            topic,
            extracted,
        )
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

    async def _xlsx_quality(self, path: Path, topic: str, *, attempt_number: int = 1) -> ArtifactQualityResult:
        local_qa = await asyncio.to_thread(validate_xlsx_path, path, topic)
        extracted = await asyncio.to_thread(extract_xlsx_text, path)
        review_qa = await review_artifact_quality(
            self.db_path,
            "xlsx",
            topic,
            extracted,
        )
        local_qa = await resolve_quality_disagreement(
            self.db_path,
            artifact_type="xlsx",
            topic=topic,
            path=path,
            local_qa=local_qa,
            review_qa=review_qa,
            extracted=extracted,
            attempt_number=attempt_number,
        )
        return local_qa.merge(review_qa)

    async def _finish(
        self,
        path: Path,
        topic: str,
        quality: ArtifactQualityResult,
        channel: str,
        run_id: str,
        source_tool: str,
        app_name: str | None,
        success_message: str | None,
        draft_message: str | None,
        open_file: bool | None,
        *,
        attempts_run: int = 1,
        repair_available: bool = True,
    ) -> BuiltArtifact:
        message = success_message or f"Done. I created {path.name}."
        if not quality.passed:
            await self.record_draft(path, f"Draft artifact rejected: {quality.summary}", run_id, source_tool)
            if channel == "imac" and not _quality_hard_block(path, quality):
                await upsert_preference(self.db_path, self.last_doc_key, str(path), source="document")
                draft = draft_message or f"I created a draft, but QA found: {quality.short_issue_text()}. I am not calling it final yet."
                reply = await self.deliver(draft, path, channel, app_name, open_file=True)
                return BuiltArtifact(path, quality, reply)
            message = qa_retry_exhausted_message(path.name, attempts_run, repair_available=repair_available)
            return BuiltArtifact(path, quality, _draft_only_reply(message))
        await self.record(path, topic, channel, f"Created artifact: {quality.summary}", run_id, source_tool)
        reply = await self.deliver(message, path, channel, app_name, open_file=open_file)
        return BuiltArtifact(path, quality, reply)

    async def record(self, path: Path, topic: str, channel: str, summary: str, run_id: str, source_tool: str) -> None:
        await upsert_preference(self.db_path, self.last_doc_key, str(path), source="document")
        await upsert_preference(self.db_path, LAST_DRAFT_DOC_KEY, "", source="document")
        await record_artifact_session(self.db_path, channel, _artifact_type(path), path, topic)
        await record_structured_artifact(
            self.db_path,
            run_id,
            local_artifact(_artifact_kind(path), str(path), summary, source_tool),
        )

    async def record_draft(self, path: Path, summary: str, run_id: str, source_tool: str) -> None:
        await upsert_preference(self.db_path, LAST_DRAFT_DOC_KEY, str(path), source="document")
        await record_structured_artifact(
            self.db_path,
            run_id,
            local_artifact(_artifact_kind(path), str(path), summary, source_tool),
        )

    async def deliver(self, message: str, path: Path, channel: str, app_name: str | None, open_file: bool | None = None) -> str:
        should_open = channel == "imac" if open_file is None else open_file
        if not should_open:
            return _attach(message, path, channel)
        summary = await asyncio.to_thread(created_file_content_summary, path)
        if not await set_current_voice_work_phase("opening", f"opening {path.name}"):
            return _attach(
                f"I cancelled that work before opening it. The file is saved in the Maya documents folder as {path.name}.",
                path,
                channel,
            )
        try:
            opened_app = await asyncio.to_thread(open_created_file, path, self.bridge, app_name)
        except Exception as exc:
            return _attach(f"{message} I saved it here: {path}. I could not open it: {exc}. {summary}", path, channel)
        save_note = f" I saved it here: {path}." if channel == "imac" else ""
        opened = opened_app or app_name or "the associated app"
        return _attach(f"{message}{save_note} I asked {opened} to open it on the iMac. {summary}", path, channel)


def _attach(message: str, path: Path, channel: str) -> str:
    return f"{message}\n[file:{path}]" if channel == "telegram" else message


def _draft_only_reply(message: str) -> str:
    if "ask me for the draft" in message.lower():
        return message
    return f"{message} I kept it as a draft and I am not calling it final. Ask me for the draft if you want to inspect it."


def _artifact_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return "spreadsheet"
    if suffix == ".pptx":
        return "presentation"
    if suffix == ".docx":
        return "document"
    if suffix == ".md":
        return "note"
    if suffix == ".html":
        return "html"
    return "file"


def _artifact_type(path: Path) -> str:
    return path.suffix.lower().lstrip(".") or "artifact"


def _quality_hard_block(path: Path, quality: ArtifactQualityResult) -> bool:
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return excel_quality_hard_block(quality)
    if suffix == ".docx":
        return docx_quality_hard_block(quality)
    return True


async def _run_rebuild(rebuild, attempt: int, quality: ArtifactQualityResult) -> None:
    result = rebuild(attempt, quality)
    if asyncio.iscoroutine(result):
        await result
