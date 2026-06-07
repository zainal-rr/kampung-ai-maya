from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from openpyxl import load_workbook

from markdown_drafter import MarkdownDraft
from storage import init_db
import travel_budget
from travel_budget import create_travel_budget_excel, save_travel_plan_fields, update_travel_plan


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
        _require(
            template_path.name.startswith("travel-budget-template-v") and template_path.suffix == ".xlsx",
            f"template file name should be short and generic: {template_path.name}",
        )
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
        _require(template_sheet.tables["DailyBudget"].ref == "A25:H39", "daily budget should provide 14 days")
        _require(template_sheet.tables["FoodRestaurantPlan"].ref == "A42:J47", "food restaurant plan should provide editable rows")
        _require(template_sheet.tables["ActualSpending"].ref == "A50:H90", "actual spending should provide 40 rows")
        _require("travel budget template" in template_reply, "reply did not describe template")
        old_draft = travel_budget.draft_markdown_with_gemini
        travel_budget.draft_markdown_with_gemini = _fake_draft
        try:
            telegram_reply = await create_travel_budget_excel(db_path, "make me a travel budget Excel", bridge, channel="telegram")
        finally:
            travel_budget.draft_markdown_with_gemini = old_draft
        _require("[file:" in telegram_reply, "Telegram travel budget reply should attach the file")
        _require("could not open" not in telegram_reply.lower(), "Telegram travel budget reply should not report desktop focus failures")
        await save_travel_plan_fields(db_path, destination="Osaka / Kyoto", departure_date="2026-08-30", return_date="2026-09-02")
        old_draft = travel_budget.draft_markdown_with_gemini
        travel_budget.draft_markdown_with_gemini = _fake_draft
        try:
            seoul_reply = await create_travel_budget_excel(
                db_path,
                "Make me an Excel budget tracker for a 2-day Seoul food trip. Include categories, estimated cost, actual cost, variance, and totals.",
                bridge,
                channel="telegram",
            )
        finally:
            travel_budget.draft_markdown_with_gemini = old_draft
        seoul_path = next((Path(marker.split("]", 1)[0]) for marker in seoul_reply.split("[file:")[1:]), None)
        _require(seoul_path is not None and seoul_path.name == "seoul-budget-tracker-v1.xlsx", "Seoul tracker filename should be concise and specific")
        seoul_book = load_workbook(seoul_path, data_only=False)
        seoul_sheet = seoul_book["Travel Budget"]
        seoul_values = [cell.value for row in seoul_sheet.iter_rows() for cell in row if cell.value not in (None, "")]
        seoul_text = " ".join(str(value) for value in seoul_values)
        _require("Seoul Budget Tracker" in seoul_text, "Seoul tracker title missing")
        _require("5-day" not in seoul_text and "culinary expedition" not in seoul_text, "Seoul tracker should not inherit or invent duration in notes")
        _require("Day 1" in seoul_text and "Day 2" in seoul_text and "Day 3" not in seoul_text, "short Seoul food tracker should default to two active days")
        _require("Estimated Cost MYR" in seoul_text and "Actual Cost MYR" in seoul_text, "Seoul tracker missing cost columns")
        _require("Variance MYR" in seoul_text and "Trip total" in seoul_text, "Seoul tracker missing variance or totals")
        _require("Food" in seoul_text, "Seoul food trip tracker missing food category")
        _require("Food And Restaurant Plan" in seoul_text, "Seoul tracker missing food and restaurant plan section")
        _require("Myeongdong Kyoja" in seoul_text and "Gwangjang Market" in seoul_text, "Seoul tracker missing restaurant-level rows")
        _require("Kalguksu and mandu" in seoul_text and "Bindaetteok" in seoul_text, "Seoul tracker missing food-level rows")
        _require("https://www.google.com/maps/search/" in seoul_text, "Seoul tracker missing restaurant source links")
        _require("Go early or off-peak" in seoul_text and "Share dishes" in seoul_text, "Seoul tracker missing useful suggestions")
        _require("=IF(OR(D43" in seoul_text and "=SUM(D43:D49)" in seoul_text, "Seoul tracker missing food variance or total formulas")
        _require(seoul_sheet["B3"].value == 1, "standalone Seoul tracker should not inherit stale saved traveler count")
        _require(seoul_sheet["A1"].fill.fgColor.rgb == "00EADCF8", "travel workbook title should use pastel fill")
        _require(seoul_sheet["A42"].fill.fgColor.rgb == "00DDEEF8", "food table header should use pastel header fill")
        _require(seoul_sheet["A43"].fill.fgColor.rgb == "00000000", "food table body should stay neutral")
        _require("2026-08-30" not in seoul_text and "Osaka / Kyoto" not in seoul_text, "standalone Seoul tracker should not inherit stale saved trip dates or destination")
        _require(
            "default until traveler count is explicit" in str(seoul_sheet["D3"].value),
            "standalone Seoul tracker should explain traveler count default",
        )
        old_draft = travel_budget.draft_markdown_with_gemini
        travel_budget.draft_markdown_with_gemini = _fake_draft
        try:
            tokyo_reply = await create_travel_budget_excel(
                db_path,
                "make me a two days food budget tracker in Excel? it is for Tokyo and for two days. the number of people is two.",
                bridge,
                channel="telegram",
            )
        finally:
            travel_budget.draft_markdown_with_gemini = old_draft
        tokyo_path = next((Path(marker.split("]", 1)[0]) for marker in tokyo_reply.split("[file:")[1:]), None)
        _require(tokyo_path is not None and tokyo_path.name == "tokyo-budget-tracker-v1.xlsx", "Tokyo voice-style tracker filename should be concise and specific")
        tokyo_book = load_workbook(tokyo_path, data_only=False)
        tokyo_sheet = tokyo_book["Travel Budget"]
        tokyo_values = [cell.value for row in tokyo_sheet.iter_rows() for cell in row if cell.value not in (None, "")]
        tokyo_text = " ".join(str(value) for value in tokyo_values)
        _require(tokyo_sheet["B2"].value == "Tokyo", "Tokyo tracker should preserve the requested destination")
        _require(tokyo_sheet["B3"].value == 2, "Tokyo tracker should preserve the spoken people count")
        _require("2-day Tokyo food trip" in tokyo_text, "Tokyo tracker should preserve the spoken duration")
        _require("Food And Restaurant Plan" in tokyo_text, "Tokyo tracker missing food and restaurant plan section")
        _require("Tsukiji Outer Market" in tokyo_text and "Gyukatsu Motomura Shinjuku" in tokyo_text, "Tokyo tracker missing restaurant-level rows")
        _require("Source Link" in tokyo_text and "Suggestion" in tokyo_text, "Tokyo tracker missing source/suggestion columns")
        _require("https://www.google.com/maps/search/" in tokyo_text, "Tokyo tracker missing restaurant source links")
        _require("=IF(OR(D43" in tokyo_text and "=SUM(D43:D49)" in tokyo_text, "Tokyo tracker missing food variance or total formulas")
        old_draft = travel_budget.draft_markdown_with_gemini
        travel_budget.draft_markdown_with_gemini = _fake_draft
        try:
            expense_reply = await create_travel_budget_excel(
                db_path,
                "give me an Excel tracker for Tokyo restaurant expenses",
                bridge,
                channel="telegram",
            )
        finally:
            travel_budget.draft_markdown_with_gemini = old_draft
        expense_path = next((Path(marker.split("]", 1)[0]) for marker in expense_reply.split("[file:")[1:]), None)
        _require(expense_path is not None and expense_path.name == "tokyo-budget-tracker-v2.xlsx", "Tokyo restaurant expense tracker should not over-capture destination words")
        expense_sheet = load_workbook(expense_path, data_only=False)["Travel Budget"]
        _require(expense_sheet["B2"].value == "Tokyo", "Tokyo restaurant expense tracker should preserve clean destination")
        old_draft = travel_budget.draft_markdown_with_gemini
        travel_budget.draft_markdown_with_gemini = _fake_draft
        try:
            stt_reply = await create_travel_budget_excel(
                db_path,
                "sheet for Tokyo Mills two days two pack",
                bridge,
                channel="telegram",
            )
        finally:
            travel_budget.draft_markdown_with_gemini = old_draft
        stt_path = next((Path(marker.split("]", 1)[0]) for marker in stt_reply.split("[file:")[1:]), None)
        _require(stt_path is not None and stt_path.name == "tokyo-budget-tracker-v3.xlsx", "Tokyo STT meal/pack artifact should route to concise tracker")
        stt_sheet = load_workbook(stt_path, data_only=False)["Travel Budget"]
        stt_values = [cell.value for row in stt_sheet.iter_rows() for cell in row if cell.value not in (None, "")]
        stt_text = " ".join(str(value) for value in stt_values)
        _require(stt_sheet["B2"].value == "Tokyo", "Tokyo STT tracker should preserve clean destination")
        _require(stt_sheet["B3"].value == 2, "Tokyo STT tracker should parse two pack as two travelers")
        _require("2-day Tokyo food trip" in stt_text, "Tokyo STT tracker should parse two days")
        _require("Tsukiji Outer Market" in stt_text and "Source Link" in stt_text and "Suggestion" in stt_text, "Tokyo STT tracker should include restaurant rows, links, and suggestions")
        old_draft = travel_budget.draft_markdown_with_gemini
        travel_budget.draft_markdown_with_gemini = _fake_draft
        try:
            mails_reply = await create_travel_budget_excel(
                db_path,
                "sheet for Tokyo Mails two days two packs",
                bridge,
                channel="telegram",
            )
        finally:
            travel_budget.draft_markdown_with_gemini = old_draft
        mails_path = next((Path(marker.split("]", 1)[0]) for marker in mails_reply.split("[file:")[1:]), None)
        _require(mails_path is not None and mails_path.name == "tokyo-budget-tracker-v4.xlsx", "Tokyo Mails STT artifact should route to concise tracker")
        mails_sheet = load_workbook(mails_path, data_only=False)["Travel Budget"]
        _require(mails_sheet["B2"].value == "Tokyo", "Tokyo Mails tracker should preserve clean destination")
        _require(mails_sheet["B3"].value == 2, "Tokyo Mails tracker should parse two packs as two travelers")
    print("travel_budget_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def _fake_draft(db_path: str, topic: str) -> MarkdownDraft:
    return MarkdownDraft("# Travel Budget Notes\n\n1) Track this 5-day Seoul culinary expedition with current estimates and actuals.\n")


if __name__ == "__main__":
    asyncio.run(main())
