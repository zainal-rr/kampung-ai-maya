from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt


CREAM = RGBColor(247, 245, 238)
INK = RGBColor(18, 34, 29)
FOREST = RGBColor(14, 71, 48)
MINT = RGBColor(221, 237, 225)
SAGE = RGBColor(118, 153, 126)
GOLD = RGBColor(190, 142, 65)
RED = RGBColor(150, 66, 58)


def build_visual_reviewed_deck(path: Path, source_slides: list[tuple[str, list[str]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    deck = Presentation()
    deck.slide_width = Inches(13.333)
    deck.slide_height = Inches(7.5)
    _cover(deck, source_slides)
    _hardware(deck)
    _ecosystem(deck)
    _tradeoffs(deck)
    _decision(deck)
    deck.save(path)


def _cover(deck: Presentation, source_slides: list[tuple[str, list[str]]]) -> None:
    slide = _slide(deck)
    _label(slide, "PRODUCT BRIEF", 0.85, 0.55, 1.7, 0.28, 9, FOREST)
    _text(slide, "Everyday glasses.\nHeads-up display.\n$799.", 0.82, 1.0, 5.45, 1.85, 40, INK, True)
    body = source_slides[0][1][0] if source_slides and source_slides[0][1] else "Monocular MicroLED display with Meta Neural Band."
    _text(slide, _clean_body(body), 0.88, 3.45, 5.2, 0.92, 15, INK, False)
    _pill(slide, "600 x 600", 0.9, 5.45)
    _pill(slide, "5,000 nits", 2.55, 5.45)
    _pill(slide, "6h mixed use", 4.2, 5.45)
    _glasses(slide, 7.0, 1.35)


def _hardware(deck: Presentation) -> None:
    slide = _slide(deck)
    _title(slide, "Hardware needs to read in sunlight")
    _stat_card(slide, "600 x 600", "MicroLED resolution", 0.8, 1.65)
    _stat_card(slide, "5,000 nits", "Peak brightness", 4.72, 1.65)
    _stat_card(slide, "6 hours", "Mixed-use battery", 8.64, 1.65)
    _note(slide, "The core claim is outdoor readability. Make brightness the visual hero, not a buried bullet.", 1.0, 5.55, 11.2)


def _ecosystem(deck: Presentation) -> None:
    slide = _slide(deck)
    _title(slide, "Input and platform are the real ecosystem bet")
    _two_column(slide, "Neural Band", "Gesture input and handwriting make the glasses feel less like a tiny phone screen.", 0.9)
    _two_column(slide, "Developer Toolkit", "Web apps and native extensions decide whether the product becomes useful beyond demos.", 6.9)
    _mini_signal(slide, "Companion device today", 3.2, 5.75)
    _mini_signal(slide, "Platform option later", 7.2, 5.75)


def _tradeoffs(deck: Presentation) -> None:
    slide = _slide(deck)
    _title(slide, "What to watch before committing")
    items = [
        ("Comfort", "Monocular HUD can create eyestrain during longer sessions.", RED),
        ("Availability", "International rollout depends on local approval and timing.", GOLD),
        ("Ecosystem", "Developer adoption is still early and unproven.", FOREST),
    ]
    for idx, (head, body, color) in enumerate(items):
        _risk_card(slide, head, body, color, 0.9 + idx * 4.05, 1.75)
    _note(slide, "This slide should feel like a decision filter, not a disclaimer paragraph.", 1.0, 5.75, 11.1)


def _decision(deck: Presentation) -> None:
    slide = _slide(deck)
    _label(slide, "DECISION GATES", 0.85, 0.58, 1.8, 0.3, 9, FOREST)
    _text(slide, "Three gates before\nyou commit", 0.82, 1.05, 4.65, 1.45, 34, INK, True)
    gates = [
        ("01", "Comfort", "Can users tolerate the monocular HUD for the real session length?"),
        ("02", "Market", "Are your target regions covered by rollout timing?"),
        ("03", "Platform", "Is the developer ecosystem mature enough now?"),
    ]
    for idx, gate in enumerate(gates):
        _gate(slide, *gate, x=5.55, y=1.15 + idx * 1.55)
    _text(slide, "Recommendation: pilot narrow use cases first, then re-check ecosystem maturity.", 0.9, 6.25, 10.9, 0.42, 14, INK, False)


def _slide(deck: Presentation, dark: bool = False):
    slide = deck.slides.add_slide(deck.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = INK if dark else CREAM
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(0.18), Inches(7.5))
    bar.fill.solid()
    bar.fill.fore_color.rgb = GOLD if dark else FOREST
    bar.line.fill.background()
    return slide


def _title(slide, text: str) -> None:
    _label(slide, "MAYA REVIEWED DECK", 0.75, 0.45, 2.2, 0.28, 8, SAGE)
    _text(slide, text, 0.75, 0.82, 10.5, 0.72, 30, INK, True)


def _stat_card(slide, number: str, label: str, x: float, y: float) -> None:
    card = _box(slide, x, y, 3.25, 1.95, MINT, SAGE)
    _text(slide, number, x + 0.34, y + 0.34, 2.42, 0.45, 30, FOREST, True)
    _text(slide, label, x + 0.36, y + 1.12, 2.25, 0.34, 15, INK, False)
    _circle(slide, x + 2.55, y + 1.12, 0.32, GOLD)


def _two_column(slide, heading: str, body: str, x: float) -> None:
    _box(slide, x, 1.65, 5.35, 3.55, RGBColor(239, 245, 238), SAGE)
    _circle(slide, x + 0.42, 2.1, 0.52, GOLD)
    _text(slide, heading, x + 1.08, 2.05, 3.7, 0.38, 24, FOREST, True)
    _text(slide, body, x + 1.08, 2.85, 3.65, 1.12, 16, INK, False)


def _risk_card(slide, heading: str, body: str, color: RGBColor, x: float, y: float) -> None:
    _box(slide, x, y, 3.35, 3.15, RGBColor(250, 248, 241), SAGE)
    _circle(slide, x + 0.35, y + 0.38, 0.36, color)
    _text(slide, heading, x + 0.85, y + 0.38, 2.0, 0.32, 22, INK, True)
    _text(slide, body, x + 0.42, y + 1.35, 2.45, 1.0, 15, INK, False)


def _gate(slide, number: str, heading: str, body: str, x: float, y: float) -> None:
    _box(slide, x, y, 6.65, 1.08, MINT, SAGE)
    _text(slide, number, x + 0.28, y + 0.24, 0.62, 0.28, 18, GOLD, True)
    _text(slide, heading, x + 1.0, y + 0.18, 1.45, 0.28, 18, FOREST, True)
    _text(slide, body, x + 2.48, y + 0.16, 3.58, 0.42, 12, INK, False)


def _glasses(slide, x: float, y: float) -> None:
    _box(slide, x, y, 2.15, 1.15, RGBColor(230, 243, 235), GOLD, radius=True)
    _box(slide, x + 2.65, y, 2.15, 1.15, RGBColor(230, 243, 235), GOLD, radius=True)
    bridge = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x + 2.05), Inches(y + 0.48), Inches(0.7), Inches(0.12))
    bridge.fill.solid()
    bridge.fill.fore_color.rgb = GOLD
    bridge.line.fill.background()
    hud = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x + 3.88), Inches(y + 0.3), Inches(0.42), Inches(0.32))
    hud.fill.solid()
    hud.fill.fore_color.rgb = FOREST
    hud.line.fill.background()
    _text(slide, "monocular HUD", x + 3.15, y + 1.55, 1.9, 0.24, 11, INK, False)


def _box(slide, x: float, y: float, w: float, h: float, fill: RGBColor, line: RGBColor, radius: bool = False):
    shape = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    item = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    item.fill.solid()
    item.fill.fore_color.rgb = fill
    item.line.color.rgb = line
    return item


def _pill(slide, text: str, x: float, y: float) -> None:
    _box(slide, x, y, 1.45, 0.52, MINT, FOREST, radius=True)
    _text(slide, text, x + 0.16, y + 0.1, 1.16, 0.3, 12, INK, True)


def _mini_signal(slide, text: str, x: float, y: float) -> None:
    _box(slide, x, y, 2.3, 0.42, MINT, SAGE, radius=True)
    _text(slide, text, x + 0.18, y + 0.1, 1.9, 0.14, 11, FOREST, True)


def _circle(slide, x: float, y: float, size: float, color: RGBColor) -> None:
    item = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(size), Inches(size))
    item.fill.solid()
    item.fill.fore_color.rgb = color
    item.line.fill.background()


def _label(slide, text: str, x: float, y: float, w: float, h: float, size: int, color: RGBColor) -> None:
    _text(slide, text, x, y, w, h, size, color, True)


def _note(slide, text: str, x: float, y: float, w: float) -> None:
    _box(slide, x, y, w, 0.74, RGBColor(236, 243, 237), SAGE)
    _text(slide, text, x + 0.26, y + 0.17, w - 0.52, 0.36, 13, INK, False)


def _text(slide, text: str, x: float, y: float, w: float, h: float, size: int, color: RGBColor, bold: bool) -> None:
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.clear()
    frame.word_wrap = True
    lines = text.split("\n") or [""]
    for idx, line in enumerate(lines):
        para = frame.paragraphs[0] if idx == 0 else frame.add_paragraph()
        para.alignment = PP_ALIGN.LEFT
        run = para.add_run()
        run.text = line
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color


def _trim(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "."


def _clean_body(text: str) -> str:
    cleaned = _trim(text, 145).strip()
    if cleaned.endswith(("Launched in", "launched in", "with", "and")):
        return "Codename Hypernova, it adds a monocular full-color MicroLED display to the right lens and ships with the Meta Neural Band."
    return cleaned
