from __future__ import annotations

import re
from html import unescape
from pathlib import Path


def created_file_content_summary(path: Path, limit: int = 420) -> str:
    """Return a short summary based on the file body, not only the filename."""
    try:
        suffix = path.suffix.lower()
        if suffix == ".md":
            return _summary_sentence(_plain_text_lines(path.read_text(encoding="utf-8", errors="ignore"), path), limit)
        if suffix == ".docx":
            from maya_documents.artifact_quality_extractors import extract_docx_text

            return _summary_sentence(_plain_text_lines(extract_docx_text(path, limit=9000), path), limit)
        if suffix == ".xlsx":
            return _xlsx_summary(path, limit)
        if suffix == ".pptx":
            return _pptx_summary(path, limit)
        if suffix == ".html":
            return _summary_sentence(_plain_text_lines(_html_to_text(path), path), limit)
    except Exception as exc:
        return f"I could not summarize the file content yet: {exc}"
    return "I could not summarize the file content yet: this file type is not supported."


def _plain_text_lines(text: str, path: Path) -> list[str]:
    stem_words = _normalize(path.stem)
    lines: list[str] = []
    for raw in str(text or "").splitlines():
        line = _clean_line(raw)
        if not line:
            continue
        normalized = _normalize(line)
        if normalized and (normalized == stem_words or normalized in {"title", "document title"}):
            continue
        lines.append(line)
    if len(lines) > 1 and _looks_like_standalone_title(lines[0]):
        lines = lines[1:]
    return lines


def _summary_sentence(lines: list[str], limit: int) -> str:
    body = [line for line in lines if len(line.split()) >= 4]
    if not body:
        body = lines[:4]
    if not body:
        return "I could not summarize the file content yet: I could not read enough body text."
    joined = " ".join(body[:4])
    return f"Content summary: {_clip(joined, limit)}"


def _xlsx_summary(path: Path, limit: int) -> str:
    from openpyxl import load_workbook

    book = load_workbook(path, data_only=False)
    sheet = book.active
    rows: list[list[str]] = []
    formula_count = 0
    for row in sheet.iter_rows(values_only=False):
        values: list[str] = []
        for cell in row:
            value = cell.value
            if isinstance(value, str) and value.startswith("="):
                formula_count += 1
            if value not in (None, ""):
                values.append(str(value))
        if values:
            rows.append(values)
        if len(rows) >= 6:
            break
    headers = rows[0] if rows else []
    sample_rows = rows[1:4] if len(rows) > 1 else []
    parts = [f"The workbook has {len(book.worksheets)} sheet{'s' if len(book.worksheets) != 1 else ''}."]
    parts.append(f"The active sheet is {sheet.title}.")
    if headers:
        parts.append(f"Its main columns are {', '.join(headers[:8])}.")
    if sample_rows:
        sample = "; ".join(" | ".join(row[:5]) for row in sample_rows[:2])
        parts.append(f"Sample rows include {sample}.")
    if formula_count:
        parts.append(f"It includes at least {formula_count} formula cell{'s' if formula_count != 1 else ''}.")
    return f"Content summary: {_clip(' '.join(parts), limit)}"


def _pptx_summary(path: Path, limit: int) -> str:
    from pptx import Presentation

    deck = Presentation(path)
    slide_bits: list[str] = []
    for index, slide in enumerate(deck.slides, start=1):
        texts: list[str] = []
        for shape in slide.shapes:
            text = getattr(shape, "text", "")
            for line in str(text or "").splitlines():
                cleaned = _clean_line(line)
                if cleaned:
                    texts.append(cleaned)
        if texts:
            body = " ".join(texts[:4])
            slide_bits.append(f"Slide {index}: {_clip(body, 110)}")
        if len(slide_bits) >= 4:
            break
    if not slide_bits:
        return "I could not summarize the file content yet: I could not read slide text."
    text = f"The deck has {len(deck.slides)} slides. " + " ".join(slide_bits)
    return f"Content summary: {_clip(text, limit)}"


def _html_to_text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    raw = re.sub(r"(?is)<script.*?</script>", " ", raw)
    raw = re.sub(r"(?is)<style.*?</style>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    return unescape(raw)


def _clean_line(raw: str) -> str:
    line = str(raw or "").strip()
    line = re.sub(r"^\s{0,3}#{1,6}\s+", "", line)
    line = re.sub(r"^\s*[-*+]\s+", "", line)
    line = re.sub(r"^\s*\d+[.)]\s+", "", line)
    line = re.sub(r"\s+", " ", line)
    return line.strip()


def _looks_like_standalone_title(line: str) -> bool:
    words = line.split()
    if len(words) > 10:
        return False
    return not any(mark in line for mark in (".", "?", ":", ";"))


def _normalize(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(text).lower()))


def _clip(text: str, limit: int) -> str:
    clean = " ".join(str(text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[: max(1, limit - 1)].rsplit(" ", 1)[0].rstrip(" ,;:") + "."
