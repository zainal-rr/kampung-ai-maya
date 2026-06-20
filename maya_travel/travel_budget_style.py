from __future__ import annotations

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.utils import get_column_letter


def _style_sheet(ws) -> None:
    header_fill = PatternFill("solid", fgColor="DDEEF8")
    title_fill = PatternFill("solid", fgColor="EADCF8")
    section_fill = PatternFill("solid", fgColor="DDF3E4")
    thin = Side(style="thin", color="D8DDE8")
    section_titles = {"Budget Snapshot", "Selected Flight", "Selected Stay", "Daily Trip Budget", "Food And Restaurant Plan", "Actual Spending", "Assumptions"}
    header_first_cells = {"Category", "Airline / option", "Provider", "Day", "Date", "Parameter"}
    for row in ws.iter_rows():
        first_value = row[0].value if row else None
        is_section = first_value in section_titles
        is_header = first_value in header_first_cells
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
            if is_section:
                cell.font = Font(bold=True, color="234E70")
                cell.fill = section_fill
            elif is_header:
                cell.font = Font(bold=True, color="234E70")
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    if ws.max_row >= 1:
        for cell in ws[1]:
            cell.font = Font(size=18, bold=True, color="40364A")
            cell.fill = title_fill
        try:
            ws.merge_cells("A1:J1")
        except ValueError:
            pass
    for column in range(1, ws.max_column + 1):
        letter = get_column_letter(column)
        max_len = max(len(str(ws.cell(row=row, column=column).value or "")) for row in range(1, min(ws.max_row, 40) + 1))
        ws.column_dimensions[letter].width = min(max(max_len + 2, 11), 34)
    ws.freeze_panes = "A2"


def _yes_no_validation(ws, cell_range: str) -> None:
    dv = DataValidation(type="list", formula1='"Yes,No"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(cell_range)


def _add_table(ws, name: str, ref: str) -> None:
    try:
        table = Table(displayName=name, ref=ref)
        style = TableStyleInfo(name="TableStyleMedium2", showFirstColumn=False, showLastColumn=False, showRowStripes=True, showColumnStripes=False)
        table.tableStyleInfo = style
        ws.add_table(table)
    except ValueError:
        pass
