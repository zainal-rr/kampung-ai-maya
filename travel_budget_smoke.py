from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from openpyxl import load_workbook

from markdown_drafter import MarkdownDraft
from storage import init_db
import travel_budget
from travel_budget import create_travel_budget_excel, update_travel_plan


class FakeBridge:
    def __init__(self):
        self.opened: list[tuple[str, str | None]] = []

    def open_file(self, path: str, app_name: str | None = None) -> None:
        self.opened.append((path, app_name))


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-travel-budget-") as tmp:
        os.environ["MAYA_TEST_MODE"] = "1"
        os.environ["MAYA_WORKSPACE_ROOT"] = str(Path(tmp) / "Maya")
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        await update_travel_plan(db_path, "keep the cheapest flight and use hotel on booking.com")
        old_draft = travel_budget.draft_markdown_with_gemini
        travel_budget.draft_markdown_with_gemini = _fake_draft
        bridge = FakeBridge()
        try:
            reply = await create_travel_budget_excel(db_path, "make an Excel travel budget sheet for this trip", bridge)
        finally:
            travel_budget.draft_markdown_with_gemini = old_draft
        path = Path(bridge.opened[0][0])
        _require(path.exists(), "workbook was not created")
        _require(bridge.opened[0][1] == "Microsoft Excel", "workbook was not opened in Excel")
        book = load_workbook(path, data_only=False)
        _require(book.sheetnames == ["Travel Budget"], "travel budget should be one sheet")
        summary = book["Travel Budget"]
        _require(summary["B3"].value == 1, "traveler count should default to one until explicit")
        _require("default until traveler count is explicit" in str(summary["D3"].value), "people source should require explicit traveler count")
        _require("cheapest" in str(summary["B4"].value).lower(), "flight preference was not saved")
        _require("booking.com" in str(summary["D4"].value).lower(), "accommodation preference was not saved")
        section_names = [summary[f"A{row}"].value for row in range(1, summary.max_row + 1)]
        for section in ("Selected Flight", "Selected Stay", "Daily Trip Budget", "Actual Spending", "Assumptions"):
            _require(section in section_names, f"missing section: {section}")
        _require("editable travel budget workbook" in reply, "reply did not describe workbook")
        old_draft = travel_budget.draft_markdown_with_gemini
        travel_budget.draft_markdown_with_gemini = _fake_draft
        try:
            template_reply = await create_travel_budget_excel(db_path, "make me a travel budget Excel", bridge)
        finally:
            travel_budget.draft_markdown_with_gemini = old_draft
        template_path = Path(bridge.opened[-1][0])
        _require(template_path.name == "travel-budget-template-v1.xlsx", "template file name should be short and generic")
        template_book = load_workbook(template_path, data_only=False)
        template_sheet = template_book["Travel Budget"]
        _require(template_sheet["A1"].value == "Travel Budget Template", "template title should be generic")
        _require(template_sheet["B2"].value in ("", None), "template destination should be blank")
        _require(template_sheet["D2"].value in ("", None), "template origin should be blank")
        _require(template_sheet["B3"].value in ("", None), "template traveler count should be blank")
        values = [cell.value for row in template_sheet.iter_rows() for cell in row]
        joined = " ".join(str(value) for value in values if value is not None)
        _require("KUL-KIX" not in joined, "template should not hardcode KUL-KIX")
        _require("Osaka / Kyoto" not in joined, "template should not hardcode Osaka / Kyoto")
        _require("Maya fills this" not in joined, "template should use neutral instructions")
        _require("DailyBudget" in template_sheet.tables, "daily budget table missing")
        _require(template_sheet.tables["DailyBudget"].ref == "A24:H38", "daily budget should provide 14 days")
        _require(template_sheet.tables["ActualSpending"].ref == "A41:H81", "actual spending should provide 40 rows")
        _require("travel budget template" in template_reply, "reply did not describe template")
        old_draft = travel_budget.draft_markdown_with_gemini
        travel_budget.draft_markdown_with_gemini = _fake_draft
        try:
            telegram_reply = await create_travel_budget_excel(db_path, "make me a travel budget Excel", bridge, channel="telegram")
        finally:
            travel_budget.draft_markdown_with_gemini = old_draft
        _require("[file:" in telegram_reply, "Telegram travel budget reply should attach the file")
        _require("could not open" not in telegram_reply.lower(), "Telegram travel budget reply should not report desktop focus failures")
    print("travel_budget_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def _fake_draft(db_path: str, topic: str) -> MarkdownDraft:
    return MarkdownDraft("# Travel Budget Notes\n\n1) Track flights, stay, daily spend, and actuals.\n")


if __name__ == "__main__":
    asyncio.run(main())
