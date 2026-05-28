from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path

from active_context import ActiveContextInspector
from docx import Document
from openpyxl import Workbook
from pptx import Presentation


class FakeBridge:
    def __init__(self, app: str, payload: dict | str):
        self.app = app
        self.payload = payload

    def get_frontmost_app(self) -> str:
        return self.app

    def _run_applescript(self, script: str) -> str:
        if isinstance(self.payload, str):
            return self.payload
        return json.dumps(self.payload)


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-active-context-") as tmp:
        root = Path(tmp) / "Maya"
        notes = root / "notes"
        notes.mkdir(parents=True)
        os.environ["MAYA_WORKSPACE_ROOT"] = str(root)

        workbook_path = Path(tmp) / "budget.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.title = "May"
        ws["A1"] = "Bank Financial Decision"
        ws["A2"] = "Risk score"
        ws["B1"] = "Decision score"
        ws["B2"] = 95
        ws["B2"] = "=SUM(B3:B8)"
        wb.save(workbook_path)
        excel = ActiveContextInspector(
            "test.db",
            FakeBridge(
                "Microsoft Excel",
                {
                    "workbook": "budget.xlsx",
                    "path": str(workbook_path),
                    "sheet": "May",
                    "range": "$B$2",
                    "values": "95",
                    "formulas": "=SUM(B3:B8)",
                    "formats": "0.00",
                },
            ),
        )
        excel_context = await excel.inspect("what does this mean", allow_screen_fallback=False)
        _require(excel_context.selection_type == "excel_selection", "Excel selection not detected")
        _require("=SUM" in excel_context.selected_content, "Excel formula missing")
        _require("Bank Financial Decision" in excel_context.document_context, "Excel document context missing")
        _require(excel_context.source == "excel_applescript_plus_xlsx_parser", "Excel source diagnostic missing")

        doc_path = Path(tmp) / "drone.docx"
        doc = Document()
        doc.core_properties.title = "Drone Requirements"
        doc.add_heading("Drone Requirements", level=1)
        doc.add_paragraph("Selected paragraph explains the drone payload and permit needs.")
        doc.save(doc_path)
        word = ActiveContextInspector(
            "test.db",
            FakeBridge("Microsoft Word", {"document": "drone.docx", "path": str(doc_path), "selection": "drone payload"}),
        )
        word_context = await word.inspect("rewrite this", allow_screen_fallback=False)
        _require("Drone Requirements" in word_context.document_context, "Word document context missing")

        deck_path = Path(tmp) / "agriculture.pptx"
        deck = Presentation()
        slide = deck.slides.add_slide(deck.slide_layouts[0])
        slide.shapes.title.text = "Agriculture Concerns in Malaysia"
        slide.placeholders[1].text = "Climate risk and smallholder financing"
        deck.save(deck_path)
        ppt = ActiveContextInspector(
            "test.db",
            FakeBridge(
                "Microsoft PowerPoint",
                {"presentation": "agriculture.pptx", "path": str(deck_path), "slide": "1", "selection": ""},
            ),
        )
        ppt_context = await ppt.inspect("does this slide make sense", allow_screen_fallback=False)
        _require("Climate risk" in ppt_context.document_context, "PowerPoint slide context missing")
        _require("highlight_status" in ppt_context.document_context, "PowerPoint highlight honesty note missing")
        _require("current slide text is reliable" in ppt_context.limits, "PowerPoint slide context limit missing")
        _require("clipboard" not in ppt_context.source, "PowerPoint should not use stale clipboard fallback")

        md_path = notes / "agentic-commerce.md"
        md_path.write_text("# Agentic Commerce\n\nSelected paragraph about checkout agents.\n", encoding="utf-8")
        text = ActiveContextInspector(
            "test.db",
            FakeBridge("Cursor", {"title": "agentic-commerce.md", "selection": "checkout agents"}),
        )
        text_context = await text.inspect("what does this mean", allow_screen_fallback=False)
        _require(text_context.selection_type == "text_selection", "Text selection not detected")
        _require("Agentic Commerce" in text_context.document_context, "Markdown document context missing")
        _require(text_context.source == "markdown_parser", "Markdown source diagnostic missing")

        no_selection_text = ActiveContextInspector(
            "test.db",
            FakeBridge("Cursor", {"title": "agentic-commerce.md", "selection": ""}),
        )
        no_selection_context = await no_selection_text.inspect("summarize this", allow_screen_fallback=False)
        _require("Agentic Commerce" in no_selection_context.document_context, "Markdown title fallback missing")

    print("active_context_smoke ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
