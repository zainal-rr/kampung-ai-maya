from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from pptx import Presentation

from active_context_parsers import MAX_EXCERPT_CHARS, ParsedDocumentContext, _clip, _safe_path, infer_markdown_path


def parse_word_context(path: str, selected_text: str = "") -> ParsedDocumentContext:
    file_path = _safe_path(path)
    if not file_path:
        return ParsedDocumentContext(limits="No readable Word document path.")
    try:
        doc = Document(file_path)
    except Exception as exc:
        return ParsedDocumentContext(limits=f"Word parser failed: {exc}")
    title = doc.core_properties.title or _first_non_empty_paragraph(doc) or _first_heading(doc) or file_path.stem
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    headings = [p.text.strip() for p in doc.paragraphs if p.text.strip() and p.style and "heading" in p.style.name.lower()]
    nearby = _near_text(paragraphs, selected_text, window=2)
    tables = _word_tables(doc)
    parts = [
        f"document_title: {title}",
        "headings:\n" + "\n".join(headings[:12]) if headings else "",
        "nearby_section:\n" + nearby if nearby else "",
        "tables:\n" + tables if tables else "",
        "document_excerpt:\n" + "\n".join(paragraphs[:80]),
    ]
    return ParsedDocumentContext(
        title=title,
        nearby_context=_clip(nearby, 2200),
        document_context=_clip("\n\n".join(part for part in parts if part), MAX_EXCERPT_CHARS),
        limits="Word document parsed from active file. Full raw document is clipped before provider context.",
        confidence_boost=0.18,
    )


def parse_powerpoint_context(path: str, slide_index: int = 1, selected_text: str = "") -> ParsedDocumentContext:
    file_path = _safe_path(path)
    if not file_path:
        return ParsedDocumentContext(limits="No readable PowerPoint path.")
    try:
        deck = Presentation(file_path)
    except Exception as exc:
        return ParsedDocumentContext(limits=f"PowerPoint parser failed: {exc}")
    titles = [_slide_title(slide) or f"Slide {idx}" for idx, slide in enumerate(deck.slides, start=1)]
    slide_index = max(1, min(slide_index or 1, len(deck.slides)))
    current_slide = deck.slides[slide_index - 1]
    title = _slide_title(current_slide) or deck.core_properties.title or f"Slide {slide_index}"
    nearby_titles = "\n".join(
        f"{idx}. {item}" for idx, item in enumerate(titles, start=1)
        if max(1, slide_index - 2) <= idx <= min(len(titles), slide_index + 2)
    )
    highlight_note = "" if selected_text else "highlight_status: exact highlighted object was not exposed by PowerPoint; use current slide text."
    parts = [
        f"deck_title: {deck.core_properties.title or title}",
        f"current_slide: {slide_index}",
        f"current_slide_title: {title}",
        highlight_note,
        "selected_object_text:\n" + selected_text if selected_text else "",
        "current_slide_text:\n" + _slide_text(current_slide),
        "speaker_notes:\n" + _slide_notes(current_slide) if _slide_notes(current_slide) else "",
        "surrounding_slide_titles:\n" + nearby_titles,
    ]
    return ParsedDocumentContext(
        title=title,
        nearby_context=_clip(nearby_titles, 1800),
        document_context=_clip("\n\n".join(part for part in parts if part), MAX_EXCERPT_CHARS),
        limits="PowerPoint parsed from active file. Exact highlighted object may be unavailable, but current slide text is reliable. Visual layout still needs screen context when layout is the question.",
        confidence_boost=0.22,
    )


def parse_markdown_context(path: str, selected_text: str = "") -> ParsedDocumentContext:
    file_path = _safe_path(path) or _find_markdown_by_hint(path)
    if not file_path:
        return ParsedDocumentContext(limits="No readable Markdown file path.")
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return ParsedDocumentContext(limits=f"Markdown parser failed: {exc}")
    title = _markdown_title(text) or file_path.stem
    headings = "\n".join(re.findall(r"^#{1,4}\s+(.+)$", text, flags=re.M)[:20])
    nearby = _markdown_nearby_section(text, selected_text)
    parts = [
        f"document_title: {title}",
        "headings:\n" + headings if headings else "",
        "nearby_section:\n" + nearby if nearby else "",
        "document_excerpt:\n" + text[:4200],
    ]
    return ParsedDocumentContext(
        title=title,
        nearby_context=_clip(nearby, 2400),
        document_context=_clip("\n\n".join(part for part in parts if part), MAX_EXCERPT_CHARS),
        limits="Markdown parsed from disk. H1 title is preferred over filename.",
        confidence_boost=0.2,
    )


def _first_heading(doc: Document) -> str:
    for paragraph in doc.paragraphs:
        if paragraph.text.strip() and paragraph.style and "heading" in paragraph.style.name.lower():
            return paragraph.text.strip()
    return ""


def _first_non_empty_paragraph(doc: Document) -> str:
    return next((p.text.strip() for p in doc.paragraphs if p.text.strip()), "")


def _near_text(items: list[str], selected_text: str, window: int = 2) -> str:
    if not items:
        return ""
    needle = selected_text.strip()
    if needle:
        for idx, item in enumerate(items):
            if needle in item or item in needle:
                return "\n".join(items[max(0, idx - window): min(len(items), idx + window + 1)])
    return "\n".join(items[: min(len(items), 8)])


def _word_tables(doc: Document) -> str:
    lines = []
    for table in doc.tables[:4]:
        for row in table.rows[:8]:
            values = [cell.text.strip().replace("\n", " ") for cell in row.cells]
            if any(values):
                lines.append(" | ".join(values))
    return "\n".join(lines)


def _slide_title(slide) -> str:
    if slide.shapes.title and slide.shapes.title.text:
        return slide.shapes.title.text.strip()
    return next((getattr(shape, "text", "").strip().splitlines()[0] for shape in slide.shapes if getattr(shape, "text", "").strip()), "")


def _slide_text(slide) -> str:
    return "\n".join(getattr(shape, "text", "").strip() for shape in slide.shapes if getattr(shape, "text", "").strip())


def _slide_notes(slide) -> str:
    try:
        return slide.notes_slide.notes_text_frame.text.strip()
    except Exception:
        return ""


def _markdown_title(text: str) -> str:
    match = re.search(r"^#\s+(.+)$", text, flags=re.M)
    return match.group(1).strip() if match else ""


def _markdown_nearby_section(text: str, selected_text: str) -> str:
    if selected_text and selected_text in text:
        idx = text.index(selected_text)
        start = text.rfind("\n#", 0, idx)
        end = text.find("\n#", idx + len(selected_text))
        return text[max(0, start if start >= 0 else idx - 900): end if end >= 0 else min(len(text), idx + 1800)].strip()
    return text[:2200].strip()


def _find_markdown_by_hint(hint: str) -> Path | None:
    inferred = infer_markdown_path(hint)
    return Path(inferred) if inferred else None
