from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import document_actions as da
from artifact_preflight import ArtifactPreflight
from markdown_drafter import MarkdownDraft
from office_modern_files import create_pptx, create_xlsx
from openpyxl import load_workbook
from pptx import Presentation
from pptx_quality_gate import PptxQualityResult
from storage import get_preference, init_db, upsert_preference

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
        try:
            da.artifact_preflight_with_gemini = _fake_preflight
            da.draft_markdown_with_gemini = _fake_draft
            da.create_powerpoint_with_qa = _fake_powerpoint_qa
            da.review_presentation_slides = _identity_review
            router = da.DocumentActionRouter(db_path, workspace=workspace)

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
            _require("updated the latest Excel workbook" in excel_reply, "xlsx edit reply wrong")
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
        finally:
            da.artifact_preflight_with_gemini = old_preflight
            da.draft_markdown_with_gemini = old_draft
            da.create_powerpoint_with_qa = old_pptx
            da.review_presentation_slides = old_review
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


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
