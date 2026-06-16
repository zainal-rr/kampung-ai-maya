from __future__ import annotations

from pathlib import Path


def extract_docx_text(path: Path, limit: int = 6000) -> str:
    from docx import Document

    doc = Document(path)
    lines = [" ".join(paragraph.text.split()) for paragraph in doc.paragraphs if paragraph.text.strip()]
    return "\n".join(lines)[:limit]


def extract_xlsx_text(path: Path, limit: int = 6000) -> str:
    from openpyxl import load_workbook

    book = load_workbook(path, data_only=False)
    lines = [f"Workbook sheet count: {len(book.worksheets)}"]
    for sheet in book.worksheets:
        lines.append(f"Worksheet: {sheet.title}")
        for row in sheet.iter_rows(values_only=True):
            values = [str(value) for value in row if value not in (None, "")]
            if values:
                lines.append(" | ".join(values))
            if len("\n".join(lines)) >= limit:
                return "\n".join(lines)[:limit]
    return "\n".join(lines)[:limit]


def summary_from_text(paragraphs: list[str], fallback: str) -> str:
    body = [item for item in paragraphs if len(item.split()) >= 4]
    if not body:
        return fallback
    joined = " ".join(body[:4])
    return clip_text(joined, 260)


def topic_needs_formula(topic: str) -> bool:
    lowered = topic.lower()
    return any(word in lowered for word in ("budget", "expense", "total", "spend", "cost", "variance", "estimated", "actual"))


def food_trip_workbook(topic: str) -> bool:
    lowered = topic.lower()
    return any(word in lowered for word in ("food trip", "restaurant", "restaurants", "food")) and any(
        word in lowered for word in ("budget", "tracker", "workbook", "excel", "spreadsheet")
    )


def clip_text(text: str, limit: int) -> str:
    clean = " ".join(str(text).split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:") + "."
