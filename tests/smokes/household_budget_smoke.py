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

from openpyxl import load_workbook

from maya_documents.artifact_builder import ArtifactBuilder
from maya_documents.document_actions_content_helpers import _budget_rows, _budget_title
from maya_documents.office_files import create_xlsx
from storage import init_db


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-household-budget-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        path = Path(tmp) / "monthly-household-budget.xlsx"
        topic = "Make a monthly household budget Excel sheet"
        headers, rows = _budget_rows(topic)
        create_xlsx(path, _budget_title(topic), headers, rows)
        book = load_workbook(path, data_only=False)
        _require(book.sheetnames == ["Budget Tracker"], f"unexpected sheet names: {book.sheetnames}")
        sheet = book["Budget Tracker"]
        _require(sheet.freeze_panes == "A4", f"expected frozen header pane at A4, got {sheet.freeze_panes!r}")
        values = [cell.value for row in sheet.iter_rows() for cell in row if cell.value not in (None, "")]
        text = " ".join(str(value) for value in values)
        for expected in ("Housing", "Utilities", "Groceries", "Phone And Internet", "Subscriptions", "Savings", "Buffer"):
            _require(expected in text, f"missing household category: {expected}")
        _require("Estimated MYR" in text and "Actual MYR" in text and "Variance MYR" in text, "missing budget columns")
        _require("=IF(OR(D4" in text and "=SUM(C4:C13)" in text, "missing variance or total formulas")
        result = await ArtifactBuilder(db_path).finish_xlsx(
            path,
            topic,
            "telegram",
            run_id="household_budget_smoke",
            source_tool="household_budget_smoke",
            label="a monthly household budget tracker",
        )
        _require(result.quality.passed, f"household budget QA failed: {result.quality.issues}")
        _require("[file:" in result.reply, "passed household budget should attach in Telegram reply")
    print("household_budget_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
