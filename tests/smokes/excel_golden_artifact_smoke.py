from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import tempfile
from pathlib import Path

from openpyxl import load_workbook

from artifact_quality import validate_xlsx_path
from document_actions import _budget_rows
from office_modern_files import create_xlsx
from travel_budget import TravelParty, _build_workbook


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-excel-golden-") as tmp:
        root = Path(tmp)
        headers, rows = _budget_rows("make me an Excel budget tracker for Tokyo from June 1 to June 3")
        generic = create_xlsx(root / "tokyo-budget.xlsx", "Tokyo Budget Tracker", headers, rows)
        generic_qa = validate_xlsx_path(generic, "budget tracker")
        _require(generic_qa.passed, f"generic budget tracker should pass: {generic_qa.issues}")
        generic_book = load_workbook(generic, data_only=False)
        generic_sheet = generic_book["Budget Tracker"]
        generic_text = _workbook_text(generic)
        _require("Variance JPY" in generic_text and "Variance MYR" in generic_text, "generic budget missing variance columns")
        _require("=SUM(E4:E10)" in generic_text and "=SUM(H4:H10)" in generic_text, "generic budget missing variance totals")
        _require(generic_sheet.freeze_panes == "A4", "generic budget should freeze the header")
        _require(generic_sheet.tables, "generic budget should include a real Excel table")

        seoul = root / "seoul-food.xlsx"
        _build_workbook(
            seoul,
            {
                "destination": "Seoul",
                "origin": "Kuala Lumpur",
                "people_count": 1,
                "people_source": "test",
                "departure_date": "",
                "return_date": "",
                "flight_preference": "not selected yet",
                "accommodation_type": "not selected yet",
                "accommodation_preference": "middle to high-end",
                "gemini_notes": "Track restaurants, markets, cafes, BBQ, and actual spend.",
            },
            TravelParty(1, "test"),
        )
        seoul_qa = validate_xlsx_path(seoul, "Excel budget tracker for a 2-day Seoul food trip")
        _require(seoul_qa.passed, f"Seoul food workbook should pass: {seoul_qa.issues}")
        seoul_text = _workbook_text(seoul)
        _require("Myeongdong Kyoja" in seoul_text and "Gwangjang Market" in seoul_text, "Seoul workbook missing restaurant rows")
        _require("Source Link" in seoul_text and "Suggestion" in seoul_text, "Seoul workbook missing source/suggestion columns")
        _require("=SUM(D43:D49)" in seoul_text and "=SUM(F43:F49)" in seoul_text, "Seoul workbook missing food totals")
        _require("https://www.google.com/maps/search/" in seoul_text, "Seoul workbook missing restaurant links")
        seoul_sheet = load_workbook(seoul, data_only=False)["Travel Budget"]
        _require(seoul_sheet["A1"].fill.fgColor.rgb == "00EADCF8", "Seoul workbook title fill missing")
        _require(seoul_sheet["A42"].fill.fgColor.rgb == "00DDEEF8", "Seoul workbook table header fill missing")
        _require(seoul_sheet["A43"].fill.fgColor.rgb == "00000000", "Seoul workbook data body should be neutral")
    print("excel_golden_artifact_smoke: ok")


def _workbook_text(path: Path) -> str:
    book = load_workbook(path, data_only=False)
    values = []
    for sheet in book.worksheets:
        values.append(f"Sheet: {sheet.title}")
        for row in sheet.iter_rows(values_only=True):
            values.extend(str(item) for item in row if item not in (None, ""))
    return "\n".join(values)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
