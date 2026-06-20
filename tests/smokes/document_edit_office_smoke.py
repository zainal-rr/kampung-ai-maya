from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import tempfile
from pathlib import Path

import maya_documents.document_actions as da
import maya_documents.document_actions_excel_mixin as excel_mixin
from maya_documents.artifact_preflight import ArtifactPreflight
from maya_documents.artifact_quality import ArtifactQualityResult
from maya_documents.document_actions_word_helpers import _document_edit_request
from maya_core.markdown_drafter import MarkdownDraft
from maya_documents.office_edit_helpers import apply_simple_xlsx_edit
from maya_documents.office_modern_files import create_docx, create_pptx, create_xlsx
from openpyxl import load_workbook
from pptx import Presentation
from maya_documents.pptx_quality_gate import PptxQualityResult
from maya_core.storage import get_preference, init_db, upsert_preference

LAST_DOC_KEY = "maya_last_document_path"


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-office-edit-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        workspace = Path(tmp) / "Maya"
        await init_db(db_path)
        old_preflight = da.artifact_preflight_with_gemini
        old_draft = da.draft_markdown_with_gemini
        old_pptx = da.create_powerpoint_with_qa
        old_review = da.review_presentation_slides
        old_artifact_review = da.review_artifact_quality
        old_excel_artifact_review = excel_mixin.review_artifact_quality
        try:
            da.artifact_preflight_with_gemini = _fake_preflight
            da.draft_markdown_with_gemini = _fake_draft
            da.create_powerpoint_with_qa = _fake_powerpoint_qa
            da.review_presentation_slides = _identity_review
            da.review_artifact_quality = _fake_artifact_review
            excel_mixin.review_artifact_quality = _fake_artifact_review
            router = da.DocumentActionRouter(db_path, workspace=workspace)

            outside = Path(tmp) / "UserFiles"
            outside.mkdir(parents=True, exist_ok=True)
            outside_docx = outside / "outside-user-file.docx"
            await asyncio.to_thread(create_docx, outside_docx, "Outside User File", [("Original", ["Do not overwrite"])])
            outside_before = outside_docx.read_bytes()
            await upsert_preference(db_path, LAST_DOC_KEY, str(outside_docx), source="polluted_state")
            outside_reply = await router.handle("/edit add a source section", "meet")
            _require("Maya-created Office artifacts" in str(outside_reply), f"outside edit should be blocked: {outside_reply}")
            _require(outside_docx.read_bytes() == outside_before, "outside docx was modified")

            outside_xlsx = outside / "outside-user-file.xlsx"
            await asyncio.to_thread(create_xlsx, outside_xlsx, "Outside User Workbook", ["Name", "Value"], [["Original", 1]])
            xlsx_before = outside_xlsx.read_bytes()
            await upsert_preference(db_path, LAST_DOC_KEY, str(outside_xlsx), source="polluted_state")
            outside_xlsx_reply = await router.handle("/edit update that workbook", "meet")
            _require("Maya-created Office artifacts" in str(outside_xlsx_reply), f"outside xlsx edit should be blocked: {outside_xlsx_reply}")
            _require(outside_xlsx.read_bytes() == xlsx_before, "outside xlsx was modified")

            inbox_docx = workspace / "inbox" / "uploaded-user-file.docx"
            inbox_docx.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(create_docx, inbox_docx, "Uploaded User File", [("Original", ["Do not overwrite"])])
            inbox_before = inbox_docx.read_bytes()
            await upsert_preference(db_path, LAST_DOC_KEY, str(inbox_docx), source="polluted_state")
            inbox_reply = await router.handle("/edit add meeting notes", "meet")
            _require("Maya-created Office artifacts" in str(inbox_reply), f"inbox docx edit should be blocked: {inbox_reply}")
            _require(inbox_docx.read_bytes() == inbox_before, "inbox docx was modified")

            notes_docx = workspace / "notes" / "uploaded-user-file.docx"
            notes_docx.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(create_docx, notes_docx, "Uploaded User Notes", [("Original", ["Do not overwrite"])])
            notes_before = notes_docx.read_bytes()
            await upsert_preference(db_path, LAST_DOC_KEY, str(notes_docx), source="polluted_state")
            notes_reply = await router.handle("/edit add meeting notes", "meet")
            _require("Maya-created Office artifacts" in str(notes_reply), f"notes docx edit should be blocked: {notes_reply}")
            _require(notes_docx.read_bytes() == notes_before, "notes docx was modified")

            _require(_document_edit_request("make that shorter and more practical") is None, "generic chat follow-up should not edit latest artifact")
            _require(_document_edit_request("Can you update that to 4 days") == ("4 days", False), "duration edit follow-up should still edit latest artifact")
            _require(
                _document_edit_request("Can you update the document to make it shorter") == ("make it shorter", False),
                "explicit document edit should remain supported",
            )
            _require(
                _document_edit_request("change the number of people in the worksheet to two") == ("the number of people in the worksheet to two", False),
                "worksheet people-count edit should route to latest artifact",
            )
            _require(
                _document_edit_request("change it to two person now?") == ("two person now?", False),
                "pronoun people-count edit should route to latest artifact",
            )
            _require(
                _document_edit_request("change that to one traveler") == ("one traveler", False),
                "singular traveler edit should route to latest artifact",
            )
            _require(
                _document_edit_request("In a Tokyo dining cost tracker, today's number of people is 2.")
                == ("today's number of people is 2 in Tokyo dining cost tracker", False),
                "contextual tracker people-count edit should route to latest artifact",
            )
            _require(
                _document_edit_request("change the day to 5 days") == ("the day to 5 days", False),
                "day-count edit should route to latest artifact",
            )
            _require(
                _document_edit_request("change the location to Tokyo") == ("the location to Tokyo", False),
                "location edit should route to latest artifact",
            )
            _require(
                _document_edit_request("update the destination to Osaka") == ("the destination to Osaka", False),
                "destination edit should route to latest artifact",
            )
            _require(
                _document_edit_request("add a simple PuTTY command section") == ("a simple PuTTY command section", False),
                "add-section follow-up should route to latest artifact edit",
            )

            pptx = workspace / "presentations" / "seoul-food-trip-deck-v1.pptx"
            await asyncio.to_thread(create_pptx, pptx, "Seoul Food Trip Deck", [("Seoul In 48 Hours", ["Food route", "Budget notes"])])
            await upsert_preference(db_path, LAST_DOC_KEY, str(pptx), source="document")
            ppt_reply = await router.handle("/edit update that to 4 days", "telegram")
            _require("updated the latest PowerPoint" in ppt_reply, "pptx edit reply wrong")
            _require(str(pptx) in ppt_reply, "pptx edit did not attach latest file")
            _require(await get_preference(db_path, LAST_DOC_KEY) == str(pptx), "pptx latest path changed unexpectedly")
            await asyncio.to_thread(Presentation, pptx)
            _require((pptx.parent / ".maya_backups").exists(), "pptx backup missing")

            xlsx = workspace / "spreadsheets" / "seoul-budget-tracker-v1.xlsx"
            await asyncio.to_thread(
                create_xlsx,
                xlsx,
                "Seoul Budget Tracker",
                ["Category", "Item", "Estimated", "Actual", "Variance", "Notes"],
                [["Food", "Lunch", 100, "", "=D4-C4", "Starter row"]],
            )
            await upsert_preference(db_path, LAST_DOC_KEY, str(xlsx), source="document")
            excel_reply = await router.handle("Can you update that with extra cafe budget", "telegram")
            _require("updated the latest Excel workbook" in excel_reply, f"xlsx edit reply wrong: {excel_reply}")
            _require(str(xlsx) in excel_reply, "xlsx edit did not attach latest file")
            book = await asyncio.to_thread(load_workbook, xlsx, data_only=False)
            formulas = [
                cell.value
                for sheet in book.worksheets
                for row in sheet.iter_rows()
                for cell in row
                if isinstance(cell.value, str) and cell.value.startswith("=")
            ]
            _require(formulas, "xlsx edit produced no formulas")
            _require(await get_preference(db_path, LAST_DOC_KEY) == str(xlsx), "xlsx latest path changed unexpectedly")

            traveler_sheet = workspace / "spreadsheets" / "traveler-count-v1.xlsx"
            book = load_workbook(xlsx)
            sheet = book.active
            sheet.insert_rows(1, 3)
            sheet["A3"] = "Travelers"
            sheet["B3"] = 2
            sheet["B5"] = "This 2-day budget is for two people, with 15,000 JPY per day for the pair."
            book.save(traveler_sheet)
            await asyncio.to_thread(apply_simple_xlsx_edit, traveler_sheet, "change that to three travelers")
            updated = await asyncio.to_thread(load_workbook, traveler_sheet, data_only=False)
            _require(updated.active["B3"].value == 3, "traveler edit should update B3")
            note = str(updated.active["B5"].value)
            _require("two people" not in note.lower() and "the pair" not in note.lower(), "traveler edit left stale people-count prose")
            _require("3 people" in note, "traveler edit did not sync people-count prose")
        finally:
            da.artifact_preflight_with_gemini = old_preflight
            da.draft_markdown_with_gemini = old_draft
            da.create_powerpoint_with_qa = old_pptx
            da.review_presentation_slides = old_review
            da.review_artifact_quality = old_artifact_review
            excel_mixin.review_artifact_quality = old_excel_artifact_review
    print("document_edit_office_smoke: ok")


async def _fake_preflight(_db_path: str, artifact_type: str, topic: str) -> ArtifactPreflight:
    return ArtifactPreflight(artifact_type, topic, "gemini", f"{artifact_type} edit preflight", True)


async def _fake_draft(_db_path: str, topic: str, _context: str = "") -> MarkdownDraft:
    if "powerpoint" in topic.lower() or "deck" in topic.lower():
        return MarkdownDraft("# Seoul In Four Days\n\n## Anchor The Food Route\n\nMarket meals\nCafe block\nDinner splurge\n")
    return MarkdownDraft("# Seoul Budget Tracker\n\n## Budget Rows\n\nFood cafe estimate\nActual spending variance\n")


async def _fake_powerpoint_qa(db_path, path, title, slides, _run_id, last_doc_key, auto_improve=True):
    await asyncio.to_thread(create_pptx, path, title, slides)
    await upsert_preference(db_path, last_doc_key, str(path), source="document")
    return PptxQualityResult(True, [], [], 0, "Design polish: good.")


async def _identity_review(_db_path, _topic, slides):
    return slides


async def _fake_artifact_review(_db_path: str, artifact_type: str, _topic: str, _extracted: str) -> ArtifactQualityResult:
    return ArtifactQualityResult(artifact_type, passed=True, summary="deterministic smoke review pass")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
