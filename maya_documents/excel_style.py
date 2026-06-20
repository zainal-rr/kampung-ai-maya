from __future__ import annotations

import re

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo


TITLE_FILL = "EADCF8"
HEADER_FILL = "DDEEF8"
DATA_FILL = "FFF9E8"
ALT_FILL = "F7F3FF"
BORDER = "D8DDE8"
TEXT = "263238"


def sheet_title_for(title: str, headers: list[str]) -> str:
    lowered = f"{title} {' '.join(headers)}".lower()
    if any(word in lowered for word in ("budget", "expense", "cost")):
        return "Budget Tracker"
    if any(word in lowered for word in ("compare", "comparison", " vs ", " versus ")):
        return "Comparison"
    if "tracker" in lowered:
        return "Tracker"
    clean = re.sub(r"[\[\]\*:/\\?]", " ", title).strip() or "Workbook"
    clean = re.sub(r"\s+", " ", clean).title()
    return clean[:31]


def style_basic_sheet(sheet, title: str, header_row: int = 3) -> None:
    thin = Side(style="thin", color=BORDER)
    sheet.freeze_panes = f"A{header_row + 1}"
    last_col = max(1, sheet.max_column)
    if last_col > 1:
        try:
            sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last_col)
        except ValueError:
            pass
    sheet["A1"].font = Font(bold=True, size=16, color=TEXT)
    sheet["A1"].fill = PatternFill("solid", fgColor=TITLE_FILL)
    for row in sheet.iter_rows():
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
            if cell.row == header_row:
                cell.font = Font(bold=True, color=TEXT)
                cell.fill = PatternFill("solid", fgColor=HEADER_FILL)
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    _format_columns(sheet, header_row)
    _add_table(sheet, title, header_row)


def _format_columns(sheet, header_row: int) -> None:
    for index in range(1, sheet.max_column + 1):
        header = str(sheet.cell(row=header_row, column=index).value or "").lower()
        letter = get_column_letter(index)
        max_len = max(len(str(sheet.cell(row=row, column=index).value or "")) for row in range(1, sheet.max_row + 1))
        sheet.column_dimensions[letter].width = min(max(max_len + 2, 12), 45)
        if any(word in header for word in ("cost", "budget", "estimate", "actual", "variance", "total", "amount", "price")):
            for row in range(header_row + 1, sheet.max_row + 1):
                sheet.cell(row=row, column=index).number_format = '#,##0.00;[Red]-#,##0.00'
        if any(word in header for word in ("status", "priority", "confidence")):
            for row in range(header_row + 1, sheet.max_row + 1):
                sheet.cell(row=row, column=index).alignment = Alignment(horizontal="center", vertical="top", wrap_text=True)


def _add_table(sheet, title: str, header_row: int) -> None:
    if sheet.max_row <= header_row or sheet.max_column < 2:
        return
    headers = [str(sheet.cell(row=header_row, column=col).value or "").strip() for col in range(1, sheet.max_column + 1)]
    if len(headers) != len(set(headers)) or any(not header for header in headers):
        return
    name = re.sub(r"[^A-Za-z0-9_]", "", title.title().replace(" ", ""))[:24] or "MayaTable"
    if not name[0].isalpha():
        name = f"Maya{name}"
    ref = f"A{header_row}:{get_column_letter(sheet.max_column)}{sheet.max_row}"
    try:
        table = Table(displayName=f"{name}Table", ref=ref)
        table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showFirstColumn=False, showLastColumn=False, showRowStripes=True, showColumnStripes=False)
        sheet.add_table(table)
    except ValueError:
        pass
