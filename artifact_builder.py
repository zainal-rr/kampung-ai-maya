from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from artifact_quality import (
    ArtifactQualityResult,
    extract_docx_text,
    extract_xlsx_text,
    review_artifact_quality,
    validate_docx_path,
    validate_xlsx_path,
)
from created_file_opener import open_created_file
from harness_artifact_store import record_structured_artifact
from harness_models import local_artifact
from storage import upsert_preference
from utils import OSBridge


LAST_DOC_KEY = "maya_last_document_path"


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
    ) -> BuiltArtifact:
        local_qa = await asyncio.to_thread(validate_docx_path, path, topic)
        review_qa = await review_artifact_quality(
            self.db_path,
            "docx",
            topic,
            await asyncio.to_thread(extract_docx_text, path),
        )
        quality = local_qa.merge(review_qa)
        return await self._finish(path, quality, channel, run_id, source_tool, app_name, success_message, draft_message, open_file)

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
    ) -> BuiltArtifact:
        local_qa = await asyncio.to_thread(validate_xlsx_path, path, topic)
        review_qa = await review_artifact_quality(
            self.db_path,
            "xlsx",
            topic,
            await asyncio.to_thread(extract_xlsx_text, path),
        )
        quality = local_qa.merge(review_qa)
        success = f"Done. I created {label}."
        draft = f"I created {label}, but QA found: {quality.short_issue_text()}. I’m keeping it as a draft."
        return await self._finish(path, quality, channel, run_id, source_tool, app_name, success, draft, open_file)

    async def _finish(
        self,
        path: Path,
        quality: ArtifactQualityResult,
        channel: str,
        run_id: str,
        source_tool: str,
        app_name: str | None,
        success_message: str | None,
        draft_message: str | None,
        open_file: bool | None,
    ) -> BuiltArtifact:
        await self.record(path, f"Created artifact: {quality.summary}", run_id, source_tool)
        message = success_message or f"Done. I created {path.name}."
        if not quality.passed:
            message = draft_message or f"I created {path.name}, but QA found: {quality.short_issue_text()}. I’m keeping it as a draft."
            if draft_message and "qa found" in draft_message.lower() and "issues" in draft_message.lower():
                message = message.replace("issues", quality.short_issue_text(), 1)
        reply = await self.deliver(message, path, channel, app_name, open_file=open_file)
        return BuiltArtifact(path, quality, reply)

    async def record(self, path: Path, summary: str, run_id: str, source_tool: str) -> None:
        await upsert_preference(self.db_path, self.last_doc_key, str(path), source="document")
        await record_structured_artifact(
            self.db_path,
            run_id,
            local_artifact(_artifact_kind(path), str(path), summary, source_tool),
        )

    async def deliver(self, message: str, path: Path, channel: str, app_name: str | None, open_file: bool | None = None) -> str:
        should_open = channel == "imac" if open_file is None else open_file
        if not should_open:
            return _attach(message, path, channel)
        try:
            opened_app = await asyncio.to_thread(open_created_file, path, self.bridge, app_name)
        except Exception as exc:
            return _attach(f"{message} I could not open it: {exc}", path, channel)
        suffix = f" in {opened_app}" if opened_app else ""
        return _attach(f"{message} I opened it on the iMac{suffix}.", path, channel)


def _attach(message: str, path: Path, channel: str) -> str:
    return f"{message}\n[file:{path}]" if channel == "telegram" else message


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
