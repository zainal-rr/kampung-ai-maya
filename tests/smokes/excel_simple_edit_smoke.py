from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from openpyxl import load_workbook

from artifact_quality import validate_xlsx_path
from office_edit_helpers import apply_simple_xlsx_edit
from office_modern_files import create_xlsx


def main() -> None:
    with TemporaryDirectory(prefix="maya-excel-edit-") as tmp:
        path = Path(tmp) / "tracker.xlsx"
        create_xlsx(
            path,
            "Office Task Tracker",
            ["Task", "Owner", "Due Date", "Status", "Priority"],
            [["Prepare weekly update", "Owner TBD", "Date TBD", "Not Started", "High"]],
        )
        apply_simple_xlsx_edit(path, "add a notes column")
        sheet = load_workbook(path, data_only=False).active
        headers = [sheet.cell(row=3, column=col).value for col in range(1, sheet.max_column + 1)]
        _require(any("Note" in str(header) for header in headers), "notes column was not added")
        quality = validate_xlsx_path(path, "office task tracker with owner due date status priority")
        _require(quality.passed, f"edited workbook failed QA: {quality.issues}")
    print("excel_simple_edit_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
