from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import os
import tempfile
import zipfile
from pathlib import Path

from maya_core.assistant import KampungAssistant
from maya_core.context_layers import init_context_layers_db
from maya_core.lesson_store import init_lesson_db
from maya_core.project_store import active_project
from maya_core.route_tracker import last_route_text
from maya_core.routine_store import init_routine_db
from session_memory_store import init_session_memory_db
from skill_store import init_skill_db
from storage import init_db, upsert_preference
from telegram_delivery import split_file_markers
from maya_documents.artifact_preflight import ArtifactPreflight
from maya_core.markdown_drafter import MarkdownDraft, _apply_source_quality, should_ground_topic
from openpyxl import load_workbook
from maya_documents.document_actions_smoke_helpers import (
    FakeBridge,
    _failure_smoke,
    _fake_artifact_quality_review,
    _fake_bad_word_edit,
    _fake_draft,
    _fake_html_draft,
    _fake_html_fallback,
    _fake_html_review,
    _fake_review,
    _first_suffix,
    _init,
    _model_draft_smoke,
    _notes_members,
    _office_can_open,
    _require,
    _slide_members,
    _source_quality_smoke,
    _workbook_text,
    _zip_has,
    _zip_text,
    same_review,
)




async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-doc-actions-") as tmp:
        old_google = os.environ.pop("GOOGLE_API_KEY", None)
        old_anthropic = os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ["MAYA_WORKSPACE_ROOT"] = str(Path(tmp) / "Maya")
        db_path = str(Path(tmp) / "smoke.db")
        root = Path(tmp) / "projects"
        (root / "orchid-lab").mkdir(parents=True)
        os.environ["MAYA_PROJECT_ROOTS"] = str(root)
        await _init(db_path)
        await upsert_preference(db_path, "pref_no_dash", "no dash symbols in answers", source="smoke")
        import maya_documents.document_actions as da
        old_draft = da.draft_markdown_with_gemini
        old_html = da.draft_html_with_artisan
        old_html_fallback = da.draft_html_with_gemini
        old_html_review = da.review_html_app
        old_should = da.should_use_model_draft
        old_review = da.review_presentation_slides
        old_artifact_review = da.review_artifact_quality
        old_preflight = da.artifact_preflight_with_gemini
        preflight_calls: list[str] = []

        async def fake_preflight(db_path: str, artifact_type: str, topic: str) -> ArtifactPreflight:
            preflight_calls.append(artifact_type)
            return ArtifactPreflight(artifact_type, topic, "gemini", f"{artifact_type} runtime preflight blueprint", True)

        da.draft_markdown_with_gemini = _fake_draft
        da.draft_html_with_artisan = _fake_html_draft
        da.draft_html_with_gemini = _fake_html_fallback
        da.review_html_app = _fake_html_review
        da.should_use_model_draft = lambda topic: True
        da.review_presentation_slides = _fake_review
        da.review_artifact_quality = _fake_artifact_quality_review
        da.artifact_preflight_with_gemini = fake_preflight
        assistant = KampungAssistant(db_path)
        bridge = FakeBridge()
        assistant.commands.documents.bridge = bridge
        assistant.commands.documents.workspace = Path(tmp) / "Maya"

        md = await assistant.handle_text("create an md file about router setup", "telegram")
        _require("router setup.md" not in md, "visible path was damaged by style cleanup")
        _, md_files = split_file_markers(md)
        _require(md_files and md_files[0].suffix == ".md" and md_files[0].exists(), "markdown file missing")
        md_text = md_files[0].read_text(encoding="utf-8")
        _require("WAN or internet port" in md_text, "router markdown content too generic")
        _require("dash style" in md_text and "dash - style" not in md_text, "markdown ignored no-dash preference")

        model_note = await assistant.handle_text("create an md file about new gemini 3.5", "telegram")
        _, model_files = split_file_markers(model_note)
        _require(model_files and model_files[0].exists(), "model note file missing")
        model_text = model_files[0].read_text(encoding="utf-8")
        _require("What To Verify" in model_text, "model note did not use research structure")
        _require("Setup Steps" not in model_text, "model note used wrong setup structure")
        _require(should_ground_topic("meta rayban display"), "current product topic was not grounded")
        write_me = await assistant.handle_text("write me an md file about hormuz street in malaysia", "telegram")
        _, write_me_files = split_file_markers(write_me)
        _require(write_me_files and write_me_files[0].suffix == ".md", "write me md wording did not create file")

        meraki = await assistant.handle_text("draft a network config for a router in md file for meraki", "telegram")
        _, meraki_files = split_file_markers(meraki)
        _require(meraki_files and meraki_files[0].exists(), "draft in md wording did not create file")
        _require("meraki" in meraki_files[0].name, "meraki file name missing topic")

        html = await assistant.handle_text("Make me a html file for an app like wonderlog", "telegram")
        html_text, html_files = split_file_markers(html)
        _require(html_files and html_files[0].suffix == ".html", "html request did not attach an html file")
        _require("```html" not in html_text and "<!DOCTYPE html>" not in html_text, "html source was pasted into chat")
        html_file_text = html_files[0].read_text(encoding="utf-8")
        _require("<!DOCTYPE html>" in html_file_text, "html file content missing doctype")
        _require("<script" in html_file_text and "<button" in html_file_text, "html file was not an interactive app")
        _require("<pre>" not in html_file_text and "### Role" not in html_file_text, "html app should not be a spec wrapper")
        _require("Reviewed by Claude" in html_file_text, "html app was not reviewed")
        html_route = await last_route_text(db_path)
        _require(
            "Codex app implementation + Claude HTML review + local HTML QA" in html_route,
            "html app should use Codex plus Claude plus local QA lane",
        )

        typo_html = await assistant.handle_text("ake me a html file for a travel planner app", "telegram")
        typo_text, typo_files = split_file_markers(typo_html)
        _require(typo_files and typo_files[0].suffix == ".html", "missing-leading-m html request did not create file")
        _require("<!DOCTYPE html>" not in typo_text, "typo html request pasted source into chat")

        docx = await assistant.handle_text("write a Word document about router setup", "telegram")
        _, docx_files = split_file_markers(docx)
        _require(docx_files and _zip_has(docx_files[0], "word/document.xml"), "docx file missing")
        _require(_zip_text(docx_files[0], "word/document.xml").count("WAN or internet"), "docx used template content")
        _require("dash - style" not in _zip_text(docx_files[0], "word/document.xml"), "docx ignored no-dash preference")
        da.draft_markdown_with_gemini = _fake_bad_word_edit
        putty_doc = await assistant.handle_text("Can you update the document to show a simple config if what i should write in putty", "telegram")
        da.draft_markdown_with_gemini = _fake_draft
        _, putty_files = split_file_markers(putty_doc)
        putty_text = _zip_text(putty_files[0], "word/document.xml") if putty_files else ""
        _require(putty_files and putty_files[0] == docx_files[0], "PuTTY edit should update router document in place")
        _require("Ument" not in putty_text, "document edit parser corrupted the title")
        _require("Router Setup Guide With PuTTY Config" in putty_text, "PuTTY edit should use a clean title")
        _require("configure terminal" in putty_text and "write memory" in putty_text, "PuTTY edit missing simple command config")
        _require("default-router" in putty_text and "show running-config" in putty_text, "PuTTY command syntax should preserve required hyphens")
        _require("Word deterministic PuTTY repair" in assistant.commands.documents.last_model_lane, "PuTTY edit should use deterministic repair if model edit is weak")
        seoul_doc = await assistant.handle_text("Make me a Word document for a 2-day Seoul food trip", "telegram")
        _, seoul_files = split_file_markers(seoul_doc)
        seoul_text = _zip_text(seoul_files[0], "word/document.xml") if seoul_files else ""
        _require(seoul_files and _zip_has(seoul_files[0], "word/document.xml"), "short Seoul doc request did not create docx")
        _require("Day 1 Plan" in seoul_text and "Day 2 Plan" in seoul_text, "decorated day headings were not canonicalized")
        _require("Gemini artifact preflight" in assistant.commands.documents.last_model_lane, "Word route did not run artifact preflight")
        edited_seoul = await assistant.handle_text("Can you update that to 4 days", "telegram")
        _, edited_seoul_files = split_file_markers(edited_seoul)
        edited_seoul_text = _zip_text(edited_seoul_files[0], "word/document.xml") if edited_seoul_files else ""
        _require(edited_seoul_files and edited_seoul_files[0] == seoul_files[0], "Word edit should update the latest document in place")
        _require("Day 4 Plan" in edited_seoul_text, "Word edit did not update the itinerary duration")
        _require((seoul_files[0].parent / ".maya_backups").exists(), "Word edit should create an internal backup")
        _require("Gemini Flash Word edit" in assistant.commands.documents.last_model_lane, "Word edit lane missing")
        copied_seoul = await assistant.handle_text("create a copy of that to 2 days", "telegram")
        _, copied_seoul_files = split_file_markers(copied_seoul)
        copied_seoul_text = _zip_text(copied_seoul_files[0], "word/document.xml") if copied_seoul_files else ""
        _require(copied_seoul_files and copied_seoul_files[0] != seoul_files[0], "explicit copy should create a new version")
        _require("Day 2 Plan" in copied_seoul_text and "Day 4 Plan" not in copied_seoul_text, "explicit copy did not apply requested edit")
        before_failed_edit = copied_seoul_files[0].read_bytes()
        da.draft_markdown_with_gemini = _fake_bad_word_edit
        failed_edit = await assistant.handle_text("update that to 9 days", "telegram")
        da.draft_markdown_with_gemini = _fake_draft
        _require("kept the original unchanged" in failed_edit, "failed Word edit should preserve original")
        _require(copied_seoul_files[0].read_bytes() == before_failed_edit, "failed in-place edit should restore original bytes")
        vague_doc = await assistant.handle_text("make me a travel doc", "telegram")
        _require("?" in vague_doc and "[file:" not in vague_doc, "vague travel doc should ask one clarification")
        voice_word = await assistant.handle_text("Give me a two days work document for Q23", "telegram", input_type="voice note")
        _, voice_word_files = split_file_markers(voice_word)
        _require(voice_word_files and _zip_has(voice_word_files[0], "word/document.xml"), "voice/STT work document wording should create docx")
        travel_doc = await assistant.handle_text("write a Word document about a pre-travel Maya testing checklist", "telegram")
        _, travel_files = split_file_markers(travel_doc)
        travel_text = _zip_text(travel_files[0], "word/document.xml") if travel_files else ""
        _require("iMac voice" in travel_text and "browser skills" in travel_text, "Maya testing doc did not use role-based testing content")
        _require("Autodesk" not in travel_text, "Maya testing doc drifted to Autodesk Maya")

        deck = await assistant.handle_text("make presentation on router setup", "telegram")
        _, deck_files = split_file_markers(deck)
        deck_path = _first_suffix(deck_files, ".pptx")
        _require(deck_path and _zip_has(deck_path, "ppt/presentation.xml"), "pptx file missing")
        _require(not _first_suffix(deck_files, ".jpg"), "PowerPoint Telegram delivery should not attach preview images by default")
        _require(_office_can_open(deck_path), "pptx should open without repair")
        deck_text = " ".join(_zip_text(deck_path, name) for name in _slide_members(deck_path))
        deck_full_text = deck_text + " " + " ".join(_zip_text(deck_path, name) for name in _notes_members(deck_path))
        _require("Key concept 1" not in deck_text, "pptx used placeholder content")
        _require("reviewed narrative" in deck_full_text.lower(), "pptx did not use review content")
        _require("Review - dash" not in deck_full_text, "pptx ignored no-dash preference")
        _require("monocular HUD" not in deck_text, "pptx QA leaked Ray-Ban revision content")
        _require("Visual QA passed" in deck, "pptx did not report QA result")
        _require("Gemini artifact preflight" in assistant.commands.documents.last_model_lane, "PowerPoint route did not run artifact preflight")
        powerpoint = await assistant.handle_text("make me a PowerPoint about Kampung AI Telegram features", "telegram")
        _, powerpoint_files = split_file_markers(powerpoint)
        powerpoint_path = _first_suffix(powerpoint_files, ".pptx")
        _require(
            powerpoint_path and _zip_has(powerpoint_path, "ppt/presentation.xml"),
            f"PowerPoint wording did not create a pptx file: {powerpoint}",
        )

        await assistant.handle_text("open project Orchid Lab", "telegram")
        project = await active_project(db_path)
        _require(project is not None, "project did not open")
        scoped = await assistant.handle_text("create an md file for this project about setup", "telegram")
        _, scoped_files = split_file_markers(scoped)
        _require(
            scoped_files and scoped_files[0].parent.resolve() == (project.path / "docs").resolve(),
            "project md not in docs",
        )

        updated = await assistant.handle_text("update this markdown with add cable notes", "telegram")
        _require("updated the Markdown file" in updated, "markdown update failed")
        _require("add cable notes" in scoped_files[0].read_text(encoding="utf-8"), "markdown update not written")

        blocked = await assistant.handle_text("create an md file about sk-test1234567890abcdef1234567890abcdef1234567890", "telegram")
        _require("can't expose sensitive" in blocked.lower(), "sensitive document was not blocked")

        imac = await assistant.handle_text("write a Word document about desk setup", "imac")
        _require("asked Microsoft Word to open it on the iMac" in imac and bridge.opened, "iMac document did not open")
        imac_md = await assistant.handle_text("create an md file about imac context test", "imac")
        _require("asked Cursor to open it on the iMac" in imac_md, "iMac markdown did not prefer Cursor")
        imac_budget = await assistant.handle_text("make me a budgeting Excel for Tokyo from June 1 to June 3 for 1 person", "imac")
        _require("travel budget workbook" in imac_budget and "Content summary:" in imac_budget and bridge.opened[-1][1] == "Microsoft Excel", "iMac budget Excel did not open")
        budget = await assistant.handle_text("make me an Excel budget tracker for Tokyo from June 1 to June 3 for 1 person", "telegram")
        _, budget_files = split_file_markers(budget)
        _require(budget_files and budget_files[0].name.startswith("tokyo-budget-tracker"), "budget tracker filename should be concise")
        budget_text = _workbook_text(budget_files[0])
        _require("Estimated Cost MYR" in budget_text and "Actual Cost MYR" in budget_text and "Selected Flight" in budget_text, "budget tracker should have editable travel budget sections")
        _require("Role And Assumptions" not in budget_text, "budget tracker should not be a notes spreadsheet")
        _require("Gemini artifact preflight" in assistant.commands.documents.last_model_lane, "Excel route did not run artifact preflight")
        sheet = await assistant.handle_text("make an Excel comparison sheet for router setup and mesh wifi", "telegram")
        _, sheet_files = split_file_markers(sheet)
        _require(sheet_files and _zip_has(sheet_files[0], "xl/worksheets/sheet1.xml"), "xlsx file missing")
        sheet_text = _zip_text(sheet_files[0], "xl/worksheets/sheet1.xml")
        _require("Option 1" not in sheet_text, "xlsx used placeholder content")
        _require("dash style" in sheet_text, "xlsx ignored no-dash preference")
        _require(_office_can_open(sheet_files[0]), "xlsx should open without repair")
        cost_sheet = await assistant.handle_text("make an Excel tracker for Kampung AI cost", "telegram")
        _, cost_files = split_file_markers(cost_sheet)
        _require(not cost_files, "retired Kampung AI cost workbook should not attach a file")
        _require("/cost" in cost_sheet, "retired Kampung AI cost workbook should point to /cost")
        _require("Grok Voice Agent" not in cost_sheet, "retired cost reply leaked old workbook lane")
        try:
            await _model_draft_smoke(db_path)
            await _failure_smoke(db_path)
            _source_quality_smoke()
            _require({"docx", "xlsx", "pptx"}.issubset(set(preflight_calls)), "preflight did not run for all Office artifact types")
            print("document_actions_smoke: ok")
        finally:
            da.draft_markdown_with_gemini = old_draft
            da.draft_html_with_artisan = old_html
            da.draft_html_with_gemini = old_html_fallback
            da.review_html_app = old_html_review
            da.should_use_model_draft = old_should
            da.review_presentation_slides = old_review
            da.review_artifact_quality = old_artifact_review
            da.artifact_preflight_with_gemini = old_preflight
            if old_google:
                os.environ["GOOGLE_API_KEY"] = old_google
            if old_anthropic:
                os.environ["ANTHROPIC_API_KEY"] = old_anthropic































if __name__ == "__main__":
    asyncio.run(main())
