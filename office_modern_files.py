from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.shared import Inches as DocxInches, Pt as DocxPt
from openpyxl import Workbook
from pptx import Presentation
from pptx.util import Inches

from office_files import safe_slug
from excel_style import sheet_title_for, style_basic_sheet
from office_pptx_palette import palette_for
from office_pptx_layout import (
    _content_slide,
    _content_slide_visual,
    _paint_background,
    _speaker_notes,
    _title_slide,
)
from office_pptx_text import _visual_bullets, _visual_title



def create_docx(path: Path, title: str, sections: list[tuple[str, list[str]]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()
    doc.add_heading(title, level=0)
    for heading, lines in sections:
        doc.add_heading(heading, level=1)
        for line in lines:
            _add_docx_line(doc, line)
    doc.save(path)
    return path


def _add_docx_line(doc: Document, line: str) -> None:
    commands = _split_command_sequence(line)
    if not commands:
        doc.add_paragraph(line)
        return
    for command in commands:
        paragraph = doc.add_paragraph()
        paragraph.paragraph_format.left_indent = DocxInches(0.25)
        paragraph.paragraph_format.space_after = DocxPt(2)
        run = paragraph.add_run(command)
        run.font.name = "Courier New"
        run.font.size = DocxPt(9)


def _split_command_sequence(line: str) -> list[str]:
    text = " ".join(str(line).split()).strip()
    lowered = text.lower()
    if not _looks_like_command_sequence(lowered):
        return []
    parts = [part.strip() for part in text.split(";") if part.strip()]
    return parts if len(parts) >= 3 else []


def _looks_like_command_sequence(lowered: str) -> bool:
    if lowered.count(";") < 2:
        return False
    markers = (
        "configure terminal",
        "write memory",
        "copy running-config",
        "show running-config",
        "ip dhcp pool",
        "default-router",
        "dns-server",
        "wpa2 psk",
        "interface gigabitethernet",
    )
    return any(re.search(rf"\b{re.escape(marker)}\b", lowered) for marker in markers)


def create_pptx(path: Path, title: str, slides: list[tuple[str, list[str]]], theme: str | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    selected_theme = theme or choose_pptx_theme(title)
    visual_topic = _pptx_visual_topic(title)
    palette = palette_for(title, selected_theme)
    deck = Presentation()
    deck.slide_width = Inches(13.333)
    deck.slide_height = Inches(7.5)
    for index, (heading, bullets) in enumerate(slides):
        slide = deck.slides.add_slide(deck.slide_layouts[6])
        _paint_background(slide, palette.background)
        visible_heading = _visual_title(heading, index)
        visible_bullets = _visual_bullets(bullets)
        if index == 0:
            _title_slide(slide, visible_heading, visible_bullets, selected_theme, palette)
        elif visual_topic:
            _content_slide_visual(slide, visible_heading, visible_bullets, index, len(slides), selected_theme, title, palette)
        else:
            _content_slide(slide, visible_heading, visible_bullets, index, len(slides), selected_theme, palette)
        _speaker_notes(slide, heading, bullets)
    deck.save(path)
    return path


def choose_pptx_theme(topic: str) -> str:
    lowered = str(topic).lower()
    pastel_markers = (
        "not dark", "no dark", "don't want dark", "dont want dark", "do not want dark",
        "not in dark", "not a dark", "avoid dark", "without dark", "pastel",
        "light theme", "light mode", "bright theme", "white theme", "soft theme",
    )
    if any(marker in lowered for marker in pastel_markers):
        return "pastel"
    return "dark"


def _pptx_visual_topic(topic: str) -> bool:
    lowered = str(topic).lower()
    markers = (
        "food", "restaurant", "cafe", "trip", "travel", "itinerary", "tourism",
        "venue", "hotel", "product", "pitch", "brand", "marketing", "lifestyle",
        "ai", "agent", "workflow", "system", "quality", "document", "artifact",
        "process", "strategy", "roadmap", "technical",
    )
    return any(marker in lowered for marker in markers)


def create_xlsx(path: Path, title: str, headers: list[str], rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    book = Workbook()
    sheet = book.active
    sheet.title = sheet_title_for(title, headers)
    sheet.append([title])
    sheet.append([])
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    style_basic_sheet(sheet, title)
    book.save(path)
    return path
