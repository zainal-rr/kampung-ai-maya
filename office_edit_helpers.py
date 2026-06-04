from __future__ import annotations

import re
import shutil
from pathlib import Path

from openpyxl import load_workbook
from pptx import Presentation

from artifact_naming import versioned_path


def backup_office_file(path: Path) -> Path:
    backup_dir = path.parent / ".maya_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = versioned_path(backup_dir / f"{path.stem}-backup-v1{path.suffix}")
    shutil.copy2(path, backup)
    return backup


def pptx_outline(path: Path, limit: int = 7000) -> str:
    deck = Presentation(path)
    lines = []
    for index, slide in enumerate(deck.slides, 1):
        texts = [" ".join(getattr(shape, "text", "").split()) for shape in slide.shapes]
        texts = [text for text in texts if text]
        notes = ""
        try:
            notes = " ".join(slide.notes_slide.notes_text_frame.text.split())
        except Exception:
            pass
        lines.append(f"Slide {index}: " + " | ".join(texts[:5]))
        if notes:
            lines.append(f"Speaker notes {index}: {notes[:600]}")
        if len("\n".join(lines)) >= limit:
            break
    return "\n".join(lines)[:limit]


def xlsx_snapshot(path: Path, limit: int = 7000) -> str:
    book = load_workbook(path, data_only=False)
    lines = []
    for sheet in book.worksheets:
        lines.append(f"Worksheet: {sheet.title}")
        for row in sheet.iter_rows(values_only=True):
            values = [str(value) for value in row if value not in (None, "")]
            if values:
                lines.append(" | ".join(values))
            if len("\n".join(lines)) >= limit:
                return "\n".join(lines)[:limit]
    return "\n".join(lines)[:limit]


def simple_xlsx_edit_instruction(instruction: str) -> bool:
    lowered = " ".join(str(instruction).lower().split())
    return any(marker in lowered for marker in ("add a notes column", "add notes column", "add a note column", "add note column"))


def apply_simple_xlsx_edit(path: Path, instruction: str) -> str:
    if not simple_xlsx_edit_instruction(instruction):
        raise ValueError("unsupported simple Excel edit")
    book = load_workbook(path)
    changed = 0
    for sheet in book.worksheets:
        header_row = _likely_header_row(sheet)
        col = sheet.max_column + 1
        header = "Additional Notes" if _row_has_notes(sheet, header_row) else "Notes"
        sheet.cell(row=header_row, column=col, value=header)
        for row in range(header_row + 1, sheet.max_row + 1):
            if any(sheet.cell(row=row, column=existing).value not in (None, "") for existing in range(1, col)):
                sheet.cell(row=row, column=col, value="Editable notes")
        changed += 1
    book.save(path)
    return f"added notes column on {changed} sheet(s)"


def _likely_header_row(sheet) -> int:
    best_row = 1
    best_count = 0
    for row in range(1, min(sheet.max_row, 12) + 1):
        count = sum(1 for cell in sheet[row] if cell.value not in (None, ""))
        if count > best_count:
            best_row, best_count = row, count
    return best_row


def _row_has_notes(sheet, row: int) -> bool:
    return any("note" in str(cell.value or "").lower() for cell in sheet[row])


def edited_office_topic(path: Path, instruction: str, current: str) -> str:
    base = re.sub(r"-v\d+$", "", path.stem).replace("-", " ").strip().title()
    day_match = re.search(r"\b(\d{1,2})\s*[- ]?\s*(?:day|days)\b", instruction, re.I)
    if day_match:
        base = re.sub(r"^\d{1,2}\s*[- ]?\s*day\s+", "", base, flags=re.I)
        return f"{int(day_match.group(1))}-day {base}"
    title = _first_title(current)
    return title or base or "Updated Maya Artifact"


def pptx_edit_request(topic: str, instruction: str, current: str) -> str:
    return (
        "Update this existing PowerPoint deck and return the full revised deck as Markdown sections.\n"
        f"Updated deck topic: {topic}\n"
        f"User edit instruction: {instruction}\n\n"
        "Rules:\n"
        "1) Preserve the useful story and replace only what conflicts with the edit.\n"
        "2) Keep visible slide text short, visual, and label-like.\n"
        "3) Put explanation in speaker-note style bullets after each slide section.\n"
        "4) Use complete, action-oriented slide titles. No fragments.\n"
        "5) Return complete slide content, not patch notes.\n\n"
        f"Current deck outline:\n{current[:7000]}"
    )


def xlsx_edit_request(topic: str, instruction: str, current: str) -> str:
    return (
        "Update this existing Excel workbook and return a complete Markdown table plan.\n"
        f"Updated workbook topic: {topic}\n"
        f"User edit instruction: {instruction}\n\n"
        "Rules:\n"
        "1) Preserve useful existing rows, formulas, categories, links, and suggestions where they still fit.\n"
        "2) Apply the edit throughout totals, assumptions, and related rows.\n"
        "3) Include formulas for totals, variance, and derived values when the workbook tracks budgets or spending.\n"
        "4) Keep the workbook immediately useful and domain-specific, not generic.\n"
        "5) Return a complete workbook table plan, not patch notes.\n\n"
        f"Current workbook snapshot:\n{current[:7000]}"
    )


def _first_title(text: str) -> str:
    for line in str(text).splitlines():
        clean = " ".join(line.split()).strip(" .")
        if clean and not clean.lower().startswith(("slide ", "worksheet:", "speaker notes")):
            return clean[:90]
    return ""
