from __future__ import annotations

from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

from office_pptx_colors import (
    DARK_ACCENT, DARK_BG, DARK_CARD, DARK_MUTED, DARK_PANEL, DARK_TEXT,
    FOREST, GOLD, INK, PASTEL_BG, PASTEL_CARD, PASTEL_PANEL, SAGE,
)
from office_pptx_text import _notes_text, _short, _slide_kicker


def _paint_background(slide, color: RGBColor) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def _title_slide(slide, title: str, bullets: list[str], theme: str) -> None:
    dark = theme == "dark"
    _accent_bar(slide, theme)
    _block(slide, 0.86, 0.88, 5.75, 5.28, DARK_PANEL if dark else FOREST, DARK_ACCENT if dark else FOREST)
    _text_box(slide, _short(title, 58, complete=False), 1.18, 1.32, 4.68, 1.22, 36, DARK_TEXT if dark else RGBColor(255, 255, 250), True)
    subtitle = _short(" / ".join(bullets[:2]) if bullets else "Visual travel plan", 78, complete=False)
    _text_box(slide, subtitle, 1.22, 3.35, 4.72, 0.82, 16, DARK_MUTED if dark else RGBColor(222, 234, 226), False)
    _hero_frame(slide, 7.06, 0.92, 5.35, 4.05, theme)


def _content_slide(slide, title: str, bullets: list[str], index: int, total: int, theme: str) -> None:
    dark = theme == "dark"
    _accent_bar(slide, theme)
    _text_box(slide, _short(title, 54, complete=False), 0.72, 0.55, 11.4, 0.7, 28, DARK_TEXT if dark else FOREST, True)
    items = bullets[:3] or ["Add a specific point."]
    pattern = index % 4
    if pattern == 1:
        for idx, bullet in enumerate(items):
            _number_card(slide, idx + 1, bullet, 0.9 + idx * 4.02, 1.75, theme)
    elif pattern == 2:
        _block(slide, 0.9, 1.55, 3.4, 4.55, DARK_PANEL if dark else PASTEL_PANEL, DARK_ACCENT if dark else SAGE)
        _text_box(slide, "Why it matters", 1.2, 2.0, 2.7, 0.45, 22, DARK_TEXT if dark else FOREST, True)
        _text_box(slide, _short(items[0], 70, complete=False), 1.22, 2.85, 2.55, 1.45, 18, DARK_MUTED if dark else INK, True)
        for idx, bullet in enumerate(items[1:] or items[:1]):
            _wide_card(slide, idx + 1, bullet, 4.85, 1.75 + idx * 1.75, theme)
    elif pattern == 3:
        _spotlight_slide(slide, items, theme)
    else:
        _timeline_slide(slide, items, theme)
    _footer(slide, index, total, theme)


def _content_slide_visual(slide, title: str, bullets: list[str], index: int, total: int, theme: str, deck_topic: str = "") -> None:
    dark = theme == "dark"
    _accent_bar(slide, theme)
    _text_box(slide, _short(title, 54, complete=False), 0.72, 0.52, 11.25, 0.72, 30, DARK_TEXT if dark else FOREST, True)
    items = bullets[:3] or ["Context", "Choice", "Next step"]
    if index % 3 == 0:
        _content_slide_visual_wide(slide, title, items, index, total, theme, deck_topic)
        return
    image_left = index % 2 == 1
    image_x = 0.8 if image_left else 6.5
    text_x = 7.15 if image_left else 0.9
    _image_panel(slide, image_x, 1.38, 5.85, 4.95, theme)
    _text_box(slide, _slide_kicker(title, deck_topic), text_x, 1.52, 3.05, 0.28, 11, DARK_ACCENT if dark else GOLD, True)
    _text_box(slide, _short(items[0], 56, complete=False), text_x, 1.96, 4.75, 1.02, 25, DARK_TEXT if dark else INK, True)
    for idx, bullet in enumerate(items[1:] or items[:1]):
        _visual_callout(slide, bullet, text_x, 3.34 + idx * 1.38, theme)
    _footer(slide, index, total, theme)


def _content_slide_visual_wide(slide, title: str, items: list[str], index: int, total: int, theme: str, deck_topic: str = "") -> None:
    dark = theme == "dark"
    _image_panel(slide, 0.86, 1.34, 11.65, 2.62, theme)
    _text_box(slide, _slide_kicker(title, deck_topic), 0.92, 4.42, 2.4, 0.28, 11, DARK_ACCENT if dark else GOLD, True)
    _text_box(slide, _short(items[0], 56, complete=False), 0.9, 4.78, 3.65, 0.7, 22, DARK_TEXT if dark else INK, True)
    for idx, bullet in enumerate(items[1:] or items[:1]):
        _visual_callout(slide, bullet, 4.95 + idx * 3.68, 4.68, theme)
    _footer(slide, index, total, theme)


def _accent_bar(slide, theme: str) -> None:
    bar = slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(0.18), Inches(7.5))
    bar.fill.solid()
    bar.fill.fore_color.rgb = DARK_ACCENT if theme == "dark" else RGBColor(24, 92, 58)
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


def _mini_card(slide, number: int, text: str, x: float, y: float, theme: str) -> None:
    dark = theme == "dark"
    _block(slide, x, y, 4.75, 1.05, DARK_CARD if dark else PASTEL_CARD, DARK_ACCENT if dark else SAGE)
    _text_box(slide, f"0{number}", x + 0.28, y + 0.28, 0.55, 0.25, 14, DARK_ACCENT if dark else GOLD, True)
    _text_box(slide, _short(text, 80, complete=False), x + 1.0, y + 0.18, 3.35, 0.72, 14, DARK_MUTED if dark else INK, False)


def _number_card(slide, number: int, text: str, x: float, y: float, theme: str) -> None:
    dark = theme == "dark"
    _block(slide, x, y, 3.25, 3.35, DARK_CARD if dark else PASTEL_PANEL, DARK_ACCENT if dark else SAGE)
    accent = slide.shapes.add_shape(1, Inches(x), Inches(y), Inches(3.25), Inches(0.12))
    accent.fill.solid()
    accent.fill.fore_color.rgb = DARK_ACCENT if dark else GOLD
    accent.line.fill.background()
    _text_box(slide, f"0{number}", x + 0.35, y + 0.35, 0.7, 0.3, 18, DARK_ACCENT if dark else GOLD, True)
    _text_box(slide, _short(text, 62, complete=False), x + 0.38, y + 1.18, 2.28, 1.2, 22, DARK_MUTED if dark else INK, True)
    dot = slide.shapes.add_shape(9, Inches(x + 2.44), Inches(y + 2.42), Inches(0.42), Inches(0.42))
    dot.fill.solid()
    dot.fill.fore_color.rgb = DARK_ACCENT if dark else GOLD
    dot.line.fill.background()


def _wide_card(slide, number: int, text: str, x: float, y: float, theme: str) -> None:
    dark = theme == "dark"
    _block(slide, x, y, 6.6, 1.25, DARK_CARD if dark else PASTEL_CARD, DARK_ACCENT if dark else SAGE)
    _text_box(slide, f"0{number}", x + 0.28, y + 0.34, 0.6, 0.3, 17, DARK_ACCENT if dark else GOLD, True)
    _text_box(slide, _short(text, 70, complete=False), x + 1.0, y + 0.28, 4.9, 0.5, 18, DARK_MUTED if dark else INK, True)


def _visual_callout(slide, text: str, x: float, y: float, theme: str) -> None:
    dark = theme == "dark"
    _block(slide, x, y, 4.95, 1.08, DARK_CARD if dark else PASTEL_CARD, DARK_ACCENT if dark else SAGE)
    accent = slide.shapes.add_shape(1, Inches(x), Inches(y), Inches(0.1), Inches(1.08))
    accent.fill.solid()
    accent.fill.fore_color.rgb = DARK_ACCENT if dark else GOLD
    accent.line.fill.background()
    _text_box(slide, _short(text, 62, complete=False), x + 0.35, y + 0.3, 4.15, 0.48, 18, DARK_MUTED if dark else INK, True)


def _spotlight_slide(slide, items: list[str], theme: str) -> None:
    dark = theme == "dark"
    _block(slide, 0.9, 1.55, 5.75, 4.55, DARK_PANEL if dark else FOREST, DARK_ACCENT if dark else FOREST)
    _text_box(slide, "Main call", 1.25, 1.98, 1.7, 0.35, 14, DARK_ACCENT if dark else GOLD, True)
    _text_box(slide, _short(items[0], 64, complete=False), 1.22, 2.65, 4.65, 1.22, 28, DARK_TEXT if dark else RGBColor(255, 255, 250), True)
    for idx, bullet in enumerate(items[1:] or items[:1]):
        _wide_card(slide, idx + 1, bullet, 7.1, 1.9 + idx * 1.72, theme)


def _timeline_slide(slide, items: list[str], theme: str) -> None:
    dark = theme == "dark"
    line = slide.shapes.add_shape(1, Inches(1.05), Inches(3.42), Inches(10.95), Inches(0.08))
    line.fill.solid()
    line.fill.fore_color.rgb = DARK_ACCENT if dark else SAGE
    line.line.fill.background()
    for idx, bullet in enumerate(items[:3]):
        x = 0.95 + idx * 4.0
        _block(slide, x, 1.75, 3.25, 3.75, DARK_CARD if dark else PASTEL_CARD, DARK_ACCENT if dark else SAGE)
        marker = slide.shapes.add_shape(9, Inches(x + 1.36), Inches(3.16), Inches(0.55), Inches(0.55))
        marker.fill.solid()
        marker.fill.fore_color.rgb = DARK_ACCENT if dark else GOLD
        marker.line.fill.background()
        _text_box(slide, f"Step {idx + 1}", x + 0.38, 2.08, 1.55, 0.32, 14, DARK_ACCENT if dark else FOREST, True)
        _text_box(slide, _short(bullet, 54, complete=False), x + 0.38, 3.95, 2.32, 0.9, 18, DARK_MUTED if dark else INK, True)


def _footer(slide, index: int, total: int, theme: str) -> None:
    dark = theme == "dark"
    footer = slide.shapes.add_textbox(Inches(10.9), Inches(6.85), Inches(1.4), Inches(0.3))
    footer.text_frame.text = f"{index + 1}/{total}"
    _set_text_style(footer, Pt(10), DARK_MUTED if dark else RGBColor(100, 112, 104))


def _hero_frame(slide, x: float, y: float, w: float, h: float, theme: str) -> None:
    dark = theme == "dark"
    _block(slide, x, y, w, h, DARK_CARD if dark else PASTEL_CARD, DARK_ACCENT if dark else SAGE)
    points = [(x + 0.72, y + 2.88), (x + 1.72, y + 1.78), (x + 3.05, y + 2.42), (x + 4.35, y + 1.24)]
    for start, end in zip(points, points[1:]):
        accent = slide.shapes.add_shape(1, Inches(start[0]), Inches(start[1]), Inches(end[0] - start[0]), Inches(0.08))
        accent.fill.solid()
        accent.fill.fore_color.rgb = DARK_ACCENT if dark else GOLD
        accent.line.fill.background()
    for idx, (px, py) in enumerate(points):
        marker = slide.shapes.add_shape(9, Inches(px - 0.16), Inches(py - 0.16), Inches(0.34), Inches(0.34))
        marker.fill.solid()
        marker.fill.fore_color.rgb = DARK_ACCENT if dark else (GOLD if idx % 2 else FOREST)
        marker.line.fill.background()
    for idx in range(3):
        block = slide.shapes.add_shape(1, Inches(x + 0.62 + idx * 1.3), Inches(y + 3.34), Inches(0.85), Inches(0.42))
        block.fill.solid()
        block.fill.fore_color.rgb = DARK_PANEL if dark else PASTEL_PANEL
        block.line.fill.background()


def _image_panel(slide, x: float, y: float, w: float, h: float, theme: str) -> None:
    dark = theme == "dark"
    _block(slide, x, y, w, h, DARK_CARD if dark else PASTEL_CARD, DARK_ACCENT if dark else SAGE)
    accent = slide.shapes.add_shape(1, Inches(x), Inches(y), Inches(w), Inches(0.12))
    accent.fill.solid()
    accent.fill.fore_color.rgb = DARK_ACCENT if dark else GOLD
    accent.line.fill.background()


def _set_text_style(shape, size: Pt, color: RGBColor, bold: bool = False) -> None:
    for paragraph in shape.text_frame.paragraphs:
        _style_paragraph(paragraph, size, color, bold)


def _style_paragraph(paragraph, size: Pt, color: RGBColor, bold: bool = False) -> None:
    for run in paragraph.runs:
        run.font.size = size
        run.font.color.rgb = color
        run.font.bold = bold


def _speaker_notes(slide, title: str, bullets: list[str]) -> None:
    try:
        frame = slide.notes_slide.notes_text_frame
        frame.clear()
        frame.text = _notes_text(title, bullets)
    except Exception:
        return
