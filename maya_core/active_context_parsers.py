from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils.cell import range_boundaries

from maya_core.workspace_paths import legacy_workspace_root, maya_workspace_root


MAX_EXCERPT_CHARS = 5200
SENSITIVE_TERMS = (
    "password",
    "passcode",
    "otp",
    "one time password",
    "card",
    "credit card",
    "debit card",
    "cvv",
    "cvc",
    "secret",
    "api key",
    "private key",
    "payment",
    "checkout",
    "booking submission",
)


@dataclass
class ParsedDocumentContext:
    title: str = ""
    nearby_context: str = ""
    document_context: str = ""
    limits: str = ""
    confidence_boost: float = 0.0


def parse_excel_context(path: str, sheet: str = "", selected_range: str = "") -> ParsedDocumentContext:
    file_path = _safe_path(path)
    if not file_path:
        return ParsedDocumentContext(limits="No readable workbook path.")
    try:
        workbook = load_workbook(file_path, data_only=False, read_only=False)
    except Exception as exc:
        return ParsedDocumentContext(limits=f"Workbook parser failed: {exc}")
    sheet_name = sheet if sheet in workbook.sheetnames else workbook.active.title
    ws = workbook[sheet_name]
    title = _first_non_empty_row(ws) or workbook.properties.title or sheet_name
    min_col, min_row, max_col, max_row = _selection_bounds(selected_range, ws.max_row, ws.max_column)
    table_min_row = max(1, min_row - 4)
    table_max_row = min(ws.max_row, max_row + 6)
    table_min_col = max(1, min_col - 3)
    table_max_col = min(ws.max_column, max_col + 5)
    selected_lines = _excel_grid(ws, min_row, max_row, min_col, max_col, include_formula=True)
    surrounding_lines = _excel_grid(ws, table_min_row, table_max_row, table_min_col, table_max_col, include_formula=False)
    comments = _excel_comments(ws, table_min_row, table_max_row, table_min_col, table_max_col)
    labels = _excel_labels(ws, min_row, min_col)
    document = [
        f"workbook_title: {title}",
        f"sheet: {sheet_name}",
        f"selected_range: {selected_range or 'unknown'}",
    ]
    if labels:
        document.append("likely_labels:\n" + labels)
    if selected_lines:
        document.append("selected_cells:\n" + selected_lines)
    if surrounding_lines:
        document.append("surrounding_table:\n" + surrounding_lines)
    if comments:
        document.append("nearby_comments:\n" + comments)
    return ParsedDocumentContext(
        title=str(title),
        nearby_context="\n\n".join(part for part in (labels, comments) if part),
        document_context=_clip("\n\n".join(document), MAX_EXCERPT_CHARS),
        limits="Workbook parsed from active file. Sensitive fields are not expected in this local workbook context.",
        confidence_boost=0.18,
    )


def infer_markdown_path(active_title: str = "", selected_text: str = "") -> str:
    hints = [active_title, selected_text[:80]]
    candidates = []
    for root in (maya_workspace_root(), legacy_workspace_root(), Path.cwd()):
        if root.exists():
            candidates.extend(path for path in root.rglob("*.md") if path.is_file())
    scored = []
    for path in candidates:
        score = 0
        text = ""
        try:
            text = path.read_text(encoding="utf-8", errors="replace")[:20000]
        except Exception:
            pass
        hay = f"{path.name}\n{text}".casefold()
        for hint in hints:
            for token in re.findall(r"[a-z0-9]{3,}", hint.casefold()):
                if token in hay:
                    score += 1
        if score:
            scored.append((score, path.stat().st_mtime, path))
    scored.sort(reverse=True)
    return str(scored[0][2]) if scored else ""


def is_sensitive_browser_context(text: str, url: str = "") -> bool:
    hay = f"{url}\n{text}".casefold()
    return any(term in hay for term in SENSITIVE_TERMS)


def _safe_path(path: str) -> Path | None:
    if not path:
        return None
    path = path.strip()
    if path.startswith("file://"):
        path = path[7:]
    if ":" in path and not path.startswith("/"):
        maybe = _hfs_to_posix(path)
        if maybe.exists():
            return maybe
    item = Path(path).expanduser()
    return item if item.exists() and item.is_file() else None


def _hfs_to_posix(path: str) -> Path:
    parts = [part for part in path.split(":") if part]
    if len(parts) > 1 and parts[0].lower() in {"macintosh hd", "imac"}:
        parts = parts[1:]
    return Path("/") / Path(*parts)


def _selection_bounds(selected_range: str, max_row: int, max_col: int) -> tuple[int, int, int, int]:
    cleaned = selected_range.replace("$", "").split(",")[0].strip()
    try:
        min_col, min_row, max_col_sel, max_row_sel = range_boundaries(cleaned)
        return min_col, min_row, max_col_sel, max_row_sel
    except Exception:
        return 1, 1, min(max_col, 8), min(max_row, 12)


def _excel_grid(ws, min_row: int, max_row: int, min_col: int, max_col: int, *, include_formula: bool) -> str:
    lines = []
    for row in ws.iter_rows(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col):
        cells = []
        for cell in row:
            value = "" if cell.value is None else str(cell.value)
            if include_formula and cell.data_type == "f":
                value = f"{value} [formula]"
            cells.append(f"{cell.coordinate}={value}")
        if any(cell.split("=", 1)[1] for cell in cells):
            lines.append(" | ".join(cells))
    return "\n".join(lines)


def _excel_comments(ws, min_row: int, max_row: int, min_col: int, max_col: int) -> str:
    lines = []
    for row in ws.iter_rows(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col):
        for cell in row:
            if cell.comment and cell.comment.text:
                lines.append(f"{cell.coordinate}: {cell.comment.text.strip()}")
    return "\n".join(lines[:20])


def _excel_labels(ws, row: int, col: int) -> str:
    labels = []
    for c in range(max(1, col - 4), col):
        value = ws.cell(row=row, column=c).value
        if value not in (None, ""):
            labels.append(f"left_label_{ws.cell(row=row, column=c).coordinate}: {value}")
    for r in range(max(1, row - 4), row):
        value = ws.cell(row=r, column=col).value
        if value not in (None, ""):
            labels.append(f"top_label_{ws.cell(row=r, column=col).coordinate}: {value}")
    return "\n".join(labels)


def _first_non_empty_row(ws) -> str:
    for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 8), max_col=min(ws.max_column, 8)):
        values = [str(cell.value).strip() for cell in row if cell.value not in (None, "")]
        if values:
            return " | ".join(values)
    return ""


def _clip(text: str, limit: int) -> str:
    text = re.sub(r"\n{3,}", "\n\n", str(text)).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 20].rstrip() + "\n[context clipped]"
