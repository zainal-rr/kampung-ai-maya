from __future__ import annotations

import os
import tempfile
import zipfile
from pathlib import Path

from maya_core.assistant import KampungAssistant
from maya_core.context_layers import init_context_layers_db
from maya_core.lesson_store import init_lesson_db
from project_store import active_project
from routine_store import init_routine_db
from session_memory_store import init_session_memory_db
from skill_store import init_skill_db
from storage import init_db, upsert_preference
from maya_documents.artifact_preflight import ArtifactPreflight
from maya_documents.artifact_quality import ArtifactQualityResult
from maya_core.markdown_drafter import MarkdownDraft, _apply_source_quality
from openpyxl import load_workbook
from telegram_delivery import split_file_markers
from maya_documents.document_actions_smoke_fakes import (
    _fake_artifact_quality_review,
    _fake_bad_word_edit,
    _fake_draft,
    _fake_html_draft,
    _fake_html_fallback,
    _fake_html_review,
    _fake_review,
    same_review,
)


class FakeBridge:
    def __init__(self):
        self.opened: list[tuple[str, str | None]] = []

    def open_file(self, path: str, app_name: str | None = None) -> None:
        self.opened.append((path, app_name))


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)
    await init_session_memory_db(db_path)
    await init_context_layers_db(db_path)


def _zip_has(path: Path, member: str) -> bool:
    with zipfile.ZipFile(path) as archive:
        return member in archive.namelist()


def _zip_text(path: Path, member: str) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read(member).decode("utf-8", errors="ignore")


def _workbook_text(path: Path) -> str:
    book = load_workbook(path, data_only=False)
    values = []
    for sheet in book.worksheets:
        for row in sheet.iter_rows(values_only=True):
            values.extend(str(item) for item in row if item is not None)
    return "\n".join(values)


def _slide_members(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        return [name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")]


def _notes_members(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        return [name for name in archive.namelist() if name.startswith("ppt/notesSlides/notesSlide") and name.endswith(".xml")]


def _first_suffix(paths: list[Path], suffix: str) -> Path | None:
    for path in paths:
        if path.suffix.lower() == suffix:
            return path
    return None


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def _model_draft_smoke(db_path: str) -> None:
    import maya_documents.document_actions as da
    from route_tracker import last_route_text

    old_draft = da.draft_markdown_with_gemini
    old_should = da.should_use_model_draft

    try:
        da.draft_markdown_with_gemini = _fake_draft
        da.should_use_model_draft = lambda topic: True
        router = da.DocumentActionRouter(db_path, workspace=Path(os.environ["MAYA_WORKSPACE_ROOT"]))
        reply = await router.handle("create an md file about new gemini 3.5", "telegram")
        _require(reply and "[file:" in reply, "model draft did not attach file")
        _require(router.last_model_lane == "Gemini Flash grounded role-based document draft", "model draft lane not recorded")
        _require(router.last_cost_recorded is True, "model draft cost not recorded")
        assistant = KampungAssistant(db_path)
        response = await assistant.handle_text("create an md file about new gemini 3.5", "telegram")
        _require("[file:" in response, "assistant model draft did not attach file")
        route = await last_route_text(db_path)
        _require("Gemini Flash grounded role-based document draft" in route, "assistant route did not expose model draft lane")
        _require("cost recorded: yes" in route, "assistant route did not record model draft cost")

        async def fake_grounded(db_path: str, topic: str) -> MarkdownDraft:
            return MarkdownDraft("# New Gemini 3.5\n\n## Sources\n\n1) Google: https://ai.google.dev\n", grounded=True)

        da.draft_markdown_with_gemini = fake_grounded
        grounded_router = da.DocumentActionRouter(db_path, workspace=Path(os.environ["MAYA_WORKSPACE_ROOT"]))
        grounded_reply = await grounded_router.handle("create an md file about latest gemini", "telegram")
        _require(grounded_reply and "[file:" in grounded_reply, "grounded draft did not attach file")
        _require(grounded_router.last_model_lane == "Gemini Flash grounded role-based document draft", "grounded lane not recorded")
    finally:
        da.draft_markdown_with_gemini = old_draft
        da.should_use_model_draft = old_should


async def _failure_smoke(db_path: str) -> None:
    import maya_documents.document_actions as da

    old_draft = da.draft_markdown_with_gemini
    old_html = da.draft_html_with_artisan
    old_fallback = da.draft_html_with_gemini
    old_review = da.review_html_app

    async def fail_draft(db_path: str, topic: str) -> MarkdownDraft:
        raise RuntimeError("429 RESOURCE_EXHAUSTED")

    async def timeout_html(db_path: str, topic: str) -> MarkdownDraft:
        raise TimeoutError("Codex timed out")

    async def no_html(db_path: str, topic: str) -> MarkdownDraft | None:
        return None

    async def no_review(db_path: str, topic: str, html: str):
        return html, "skipped"

    async def broken_review(db_path: str, topic: str, html: str):
        return "<!DOCTYPE html>\n<html><head><style>body{", "reviewed"

    try:
        da.draft_markdown_with_gemini = fail_draft
        da.review_html_app = no_review
        router = da.DocumentActionRouter(db_path, workspace=Path(os.environ["MAYA_WORKSPACE_ROOT"]))
        before = set(Path(os.environ["MAYA_WORKSPACE_ROOT"]).joinpath("notes").glob("quota-test*.md"))
        reply = await router.handle("create an md file about quota test", "telegram")
        after = set(Path(os.environ["MAYA_WORKSPACE_ROOT"]).joinpath("notes").glob("quota-test*.md"))
        _require("No file was created" in (reply or ""), "quota failure should not create fake file")
        _require(before == after, "quota failure created a file")
        da.draft_html_with_artisan = timeout_html
        da.draft_html_with_gemini = _fake_html_fallback
        fallback_reply = await router.handle("make me a html file for a travel planner app", "telegram")
        _require("[file:" in (fallback_reply or ""), "Gemini should take over when Codex times out")
        _require(
            router.last_model_lane == "Codex app implementation timeout -> Gemini Flash HTML fallback + local HTML QA",
            "fallback lane should record the Codex timeout before Gemini takeover",
        )
        da.draft_html_with_gemini = no_html
        html_reply = await router.handle("make me a html file for a travel planner app", "telegram")
        _require("Codex app lane and Gemini" in (html_reply or ""), "double HTML failure should be reported")
        _require("No file was created" in (html_reply or ""), "Codex timeout should not claim a file")
        da.draft_html_with_artisan = _fake_html_draft
        da.draft_html_with_gemini = _fake_html_fallback
        da.review_html_app = broken_review
        broken_reply = await router.handle("make me a html file for a broken review check app", "telegram")
        _, broken_files = split_file_markers(broken_reply or "")
        _require(broken_files and broken_files[0].exists(), "broken review should still create original html")
        broken_text = broken_files[0].read_text(encoding="utf-8")
        _require("<script" in broken_text and "<button" in broken_text, "broken review replaced the usable original")
        _require(
            router.last_model_lane == "Codex app implementation + Claude HTML review rejected + local HTML QA",
            "broken Claude review should be marked rejected",
        )
        _require("draft" in (broken_reply or "").lower() and "Done. I created" not in (broken_reply or ""), "rejected HTML review should not be called done")
        da.review_html_app = same_review
        same_reply = await router.handle("make me a html file for a same review check app", "telegram")
        _require("[file:" in (same_reply or ""), "same review should still create html")
        _require(
            router.last_model_lane == "Codex app implementation + Claude HTML review + local HTML QA",
            "valid same Claude review should be recorded",
        )
    finally:
        da.draft_markdown_with_gemini = old_draft
        da.draft_html_with_artisan = old_html
        da.draft_html_with_gemini = old_fallback
        da.review_html_app = old_review
















def _office_can_open(path: Path) -> bool:
    if path.suffix == ".pptx":
        from pptx import Presentation
        Presentation(path)
        return True
    if path.suffix == ".xlsx":
        from openpyxl import load_workbook
        load_workbook(path)
        return True
    if path.suffix == ".docx":
        from docx import Document
        Document(path)
        return True
    return False


def _source_quality_smoke() -> None:
    text = "# Gemini\n\n## Overview\n\n1) Draft.\n\n### Sources\n\n1) Old source\n"
    sources = [
        ("Google AI", "https://ai.google.dev/gemini-api/docs"),
        ("simonwillison.net", "https://vertexaisearch.cloud.google.com/grounding-api-redirect/fake"),
        ("meta.com", "https://vertexaisearch.cloud.google.com/grounding-api-redirect/fake2"),
    ]
    cleaned = _apply_source_quality(text, sources)
    _require(cleaned.count("## Sources") == 1, "source section duplicated")
    _require("### Sources" not in cleaned, "model source heading survived")
    _require("### Official Sources" in cleaned, "official sources not labeled")
    _require("### Third Party Sources" in cleaned, "third party sources not labeled")
    _require("simonwillison.net" in cleaned, "redirected third party source missing")
    _require("meta.com" in cleaned.split("### Third Party Sources")[0], "official redirect title not recognized")
    _require("Old source" not in cleaned, "old model sources were not replaced")
