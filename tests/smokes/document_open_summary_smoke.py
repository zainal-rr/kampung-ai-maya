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

from maya_documents.artifact_builder import ArtifactBuilder
from maya_documents.document_actions import DocumentActionRouter
from storage import init_db


class FakeBridge:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.opened: list[tuple[str, str | None]] = []
        self.scripts: list[str] = []
        self.unsaved_word = False

    def open_file(self, path: str, app_name: str | None = None) -> None:
        if self.fail:
            raise RuntimeError("open blocked in smoke")
        self.opened.append((path, app_name))

    def _run_applescript(self, script: str) -> str:
        self.scripts.append(script)
        return "unsaved_open_copy" if self.unsaved_word else "opened"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _make_docx(path: Path) -> None:
    from docx import Document

    doc = Document()
    doc.add_heading("Kazakhstan Hiking Trip", level=1)
    doc.add_paragraph("This plan focuses on mountain hiking near Almaty, lake scenery, and a nine day pacing window.")
    doc.add_paragraph("It includes route assumptions, lodging notes, transport reminders, and safety checks for remote trails.")
    doc.save(path)


def _make_xlsx(path: Path) -> None:
    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    sheet.title = "Travel Budget"
    sheet.append(["Category", "Item", "Estimated MYR", "Actual MYR", "Variance"])
    sheet.append(["Flights", "Kuala Lumpur to Almaty", 2400, "", "=D2-C2"])
    sheet.append(["Accommodation", "Mountain lodge and city hotel", 3500, "", "=D3-C3"])
    book.save(path)


def _make_pptx(path: Path) -> None:
    from pptx import Presentation

    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[1])
    slide.shapes.title.text = "Malaysia Agriculture Concerns"
    slide.placeholders[1].text = "Food security, climate pressure, farmer income, and irrigation gaps."
    slide = deck.slides.add_slide(deck.slide_layouts[1])
    slide.shapes.title.text = "Actions"
    slide.placeholders[1].text = "Modernize irrigation, support smallholders, improve data collection, and manage crop risk."
    deck.save(path)


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-open-summary-") as tmp:
        root = Path(tmp)
        db_path = str(root / "smoke.db")
        await init_db(db_path)
        bridge = FakeBridge()
        router = DocumentActionRouter(db_path, workspace=root / "Maya", bridge=bridge)

        md = root / "agentic-commerce-v1.md"
        md.write_text(
            "# Agentic Commerce\n\n"
            "Agentic commerce lets software agents compare products, negotiate constraints, and prepare purchases for human approval.\n\n"
            "The important parts are identity, consent, payment safety, merchant trust, and audit logs.\n",
            encoding="utf-8",
        )
        md_reply = await router._done("Markdown draft", md, "imac", None)
        _require("asked" in md_reply and "to open it on the iMac" in md_reply, "Markdown iMac reply did not open")
        _require("identity, consent, payment safety" in md_reply, "Markdown summary did not use file content")
        md_summary = md_reply.split("Content summary:", 1)[-1].lower()
        _require("agentic commerce lets software agents" in md_summary, "Markdown summary read title instead of body")

        docx = root / "kazakhstan-hiking-v1.docx"
        _make_docx(docx)
        docx_reply = await router._done("Word draft", docx, "imac", "Microsoft Word")
        _require("asked Microsoft Word to open it on the iMac" in docx_reply, "Word iMac reply did not open Word")
        _require("mountain hiking near Almaty" in docx_reply, "Word summary did not use document body")
        word_script = "\n".join(bridge.scripts)
        _require("close d saving no" in word_script, "Word opener should refresh saved open copies from disk")
        _require("unsaved_open_copy" in word_script, "Word opener should detect unsaved open copies")

        unsaved_bridge = FakeBridge()
        unsaved_bridge.unsaved_word = True
        unsaved_router = DocumentActionRouter(db_path, workspace=root / "Maya", bridge=unsaved_bridge)
        unsaved_reply = await unsaved_router._done("Word draft", docx, "imac", "Microsoft Word")
        _require("could not open it" in unsaved_reply.lower(), "unsaved Word copy should not be force-reloaded")

        xlsx = root / "travel-budget-v1.xlsx"
        _make_xlsx(xlsx)
        xlsx_reply = await router._done("Excel draft", xlsx, "imac", "Microsoft Excel")
        _require("asked Microsoft Excel to open it on the iMac" in xlsx_reply, "Excel iMac reply did not open Excel")
        _require("Category, Item, Estimated MYR" in xlsx_reply, "Excel summary did not include workbook columns")
        _require("Kuala Lumpur to Almaty" in xlsx_reply, "Excel summary did not include workbook row content")

        pptx = root / "agriculture-concerns-v1.pptx"
        _make_pptx(pptx)
        pptx_reply = await router._done_powerpoint("PowerPoint draft", pptx, "imac", "agriculture concerns in Malaysia")
        _require("asked Microsoft PowerPoint to open it on the iMac" in pptx_reply, "PowerPoint reply did not open PowerPoint")
        _require("Food security" in pptx_reply and "Modernize irrigation" in pptx_reply, "PowerPoint summary did not use slide content")

        failing = DocumentActionRouter(db_path, workspace=root / "Maya", bridge=FakeBridge(fail=True))
        fail_reply = await failing._done("Markdown draft", md, "imac", None)
        _require(str(md) in fail_reply, "open failure did not tell user where the file is")
        _require("I could not open it" in fail_reply, "open failure did not report open error")
        _require("identity, consent, payment safety" in fail_reply, "open failure did not still summarize content")

        builder = ArtifactBuilder(db_path, bridge)
        builder_reply = await builder.deliver("Done. I created an editable travel budget template.", xlsx, "imac", "Microsoft Excel")
        _require("asked Microsoft Excel to open it on the iMac" in builder_reply, "ArtifactBuilder did not open iMac file")
        _require("Kuala Lumpur to Almaty" in builder_reply, "ArtifactBuilder did not include content summary")

        telegram_reply = await router._done("Markdown draft", md, "telegram", None)
        _require("[file:" in telegram_reply, "Telegram delivery should still attach the file")
        _require("Content summary:" not in telegram_reply, "Telegram document delivery should not add iMac summary")

    print("document_open_summary_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
