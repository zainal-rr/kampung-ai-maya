from __future__ import annotations

from pathlib import Path

from docx import Document
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

from office_files import presentation_outline, safe_slug


CREAM = RGBColor(248, 247, 242)
INK = RGBColor(23, 35, 31)
FOREST = RGBColor(16, 88, 57)
MINT = RGBColor(224, 238, 229)
GOLD = RGBColor(194, 146, 63)
SAGE = RGBColor(143, 166, 148)


def create_docx(path: Path, title: str, sections: list[tuple[str, list[str]]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()
    doc.add_heading(title, level=0)
    for heading, lines in sections:
        doc.add_heading(heading, level=1)
        for line in lines:
            doc.add_paragraph(line)
    doc.save(path)
    return path


def create_pptx(path: Path, title: str, slides: list[tuple[str, list[str]]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    deck = Presentation()
    deck.slide_width = Inches(13.333)
    deck.slide_height = Inches(7.5)
    for index, (heading, bullets) in enumerate(slides):
        slide = deck.slides.add_slide(deck.slide_layouts[6])
        _paint_background(slide, RGBColor(248, 250, 247))
        if index == 0:
            _title_slide(slide, heading, bullets)
        else:
            _content_slide(slide, heading, bullets, index, len(slides))
    deck.save(path)
    return path


def create_xlsx(path: Path, title: str, headers: list[str], rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    book = Workbook()
    sheet = book.active
    sheet.title = "Maya Draft"
    sheet.append([title])
    sheet.append([])
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    _style_sheet(sheet)
    book.save(path)
    return path


def _paint_background(slide, color: RGBColor) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def _title_slide(slide, title: str, bullets: list[str]) -> None:
    _accent_bar(slide)
    _block(slide, 0.95, 0.9, 6.0, 5.65, FOREST, FOREST)
    _text_box(slide, title, 1.25, 1.35, 5.05, 1.3, 34, RGBColor(255, 255, 250), True)
    subtitle = _complete(" ".join(bullets[:1])) if bullets else "Draft prepared by Maya"
    _text_box(slide, subtitle, 1.28, 3.25, 4.95, 1.0, 17, RGBColor(222, 234, 226), False)
    cards = bullets[1:4] or ["Context", "Implication", "Next step"]
    for idx, line in enumerate(cards[:3]):
        _mini_card(slide, idx + 1, line, 7.35, 1.08 + idx * 1.55)


def _content_slide(slide, title: str, bullets: list[str], index: int, total: int) -> None:
    _accent_bar(slide)
    _text_box(slide, title, 0.72, 0.55, 11.4, 0.7, 26, FOREST, True)
    items = bullets[:3] or ["Add a specific point."]
    if index % 2:
        for idx, bullet in enumerate(items):
            _number_card(slide, idx + 1, bullet, 0.9 + idx * 4.02, 1.75)
    else:
        _block(slide, 0.9, 1.55, 3.4, 4.55, MINT, SAGE)
        _text_box(slide, "Why it matters", 1.2, 2.0, 2.7, 0.45, 22, FOREST, True)
        _text_box(slide, _short(items[0], 150), 1.22, 2.85, 2.55, 1.45, 15, INK, False)
        for idx, bullet in enumerate(items[1:] or items[:1]):
            _wide_card(slide, idx + 1, bullet, 4.85, 1.75 + idx * 1.75)
    footer = slide.shapes.add_textbox(Inches(10.9), Inches(6.85), Inches(1.4), Inches(0.3))
    footer.text_frame.text = f"{index + 1}/{total}"
    _set_text_style(footer, Pt(10), RGBColor(100, 112, 104))


def _accent_bar(slide) -> None:
    bar = slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(0.18), Inches(7.5))
    bar.fill.solid()
    bar.fill.fore_color.rgb = RGBColor(24, 92, 58)
    bar.line.fill.background()


def _block(slide, x: float, y: float, w: float, h: float, fill: RGBColor, line: RGBColor):
    shape = slide.shapes.add_shape(1, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.color.rgb = line
    return shape


def _text_box(slide, text: str, x: float, y: float, w: float, h: float, size: int, color: RGBColor, bold: bool):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.clear()
    frame.word_wrap = True
    para = frame.paragraphs[0]
    run = para.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.color.rgb = color
    run.font.bold = bold
    return box


def _mini_card(slide, number: int, text: str, x: float, y: float) -> None:
    _block(slide, x, y, 4.75, 1.05, RGBColor(255, 255, 252), SAGE)
    _text_box(slide, f"0{number}", x + 0.28, y + 0.28, 0.55, 0.25, 14, GOLD, True)
    _text_box(slide, _short(text, 155), x + 1.0, y + 0.18, 3.35, 0.72, 13, INK, False)


def _number_card(slide, number: int, text: str, x: float, y: float) -> None:
    _block(slide, x, y, 3.25, 3.35, MINT, SAGE)
    _text_box(slide, f"0{number}", x + 0.35, y + 0.35, 0.7, 0.3, 18, GOLD, True)
    _text_box(slide, _short(text, 190), x + 0.38, y + 0.95, 2.45, 1.95, 14, INK, False)


def _wide_card(slide, number: int, text: str, x: float, y: float) -> None:
    _block(slide, x, y, 6.6, 1.25, RGBColor(255, 255, 252), SAGE)
    _text_box(slide, f"0{number}", x + 0.28, y + 0.34, 0.6, 0.3, 17, GOLD, True)
    _text_box(slide, _short(text, 220), x + 1.0, y + 0.18, 4.9, 0.8, 13, INK, False)


def _short(text: str, limit: int = 90) -> str:
    clean = " ".join(str(text).split())
    if len(clean) <= limit:
        return _complete(clean)
    for punctuation in (". ", "? ", "! "):
        pos = clean.rfind(punctuation, 0, limit)
        if pos >= 35:
            return clean[: pos + 1]
    for separator in (" — ", " - ", "; ", ": "):
        first = clean.split(separator, 1)[0].strip()
        if 35 <= len(first) <= limit:
            return first.rstrip(".") + "."
    clipped = clean[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return clipped.rstrip(".") + "."


def _complete(text: str) -> str:
    clean = text.strip(" ,;:-")
    return clean if clean.endswith((".", "?", "!", ")")) else clean + "."


def _set_text_style(shape, size: Pt, color: RGBColor, bold: bool = False) -> None:
    for paragraph in shape.text_frame.paragraphs:
        _style_paragraph(paragraph, size, color, bold)


def _style_paragraph(paragraph, size: Pt, color: RGBColor, bold: bool = False) -> None:
    for run in paragraph.runs:
        run.font.size = size
        run.font.color.rgb = color
        run.font.bold = bold


def _style_sheet(sheet) -> None:
    sheet["A1"].font = Font(bold=True, size=14)
    header_row = 3
    fill = PatternFill("solid", fgColor="E8F0FE")
    for cell in sheet[header_row]:
        cell.font = Font(bold=True)
        cell.fill = fill
    for column in sheet.columns:
        letter = column[0].column_letter
        width = min(max(len(str(cell.value or "")) for cell in column) + 2, 55)
        sheet.column_dimensions[letter].width = width
    sheet.freeze_panes = "A4"
