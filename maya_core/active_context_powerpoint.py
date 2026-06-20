from __future__ import annotations

import re

from pptx import Presentation

from maya_core.active_context_document_parsers import parse_powerpoint_context
from maya_core.active_context_models import ActiveContext


def verify_powerpoint_visible_context(base: ActiveContext, screen_text: str) -> ActiveContext:
    if not base.active_file or not screen_text:
        return base
    visible_slide, visible_title = _visible_slide(screen_text, base.active_file)
    if not visible_slide:
        return base
    applescript_slide = _applescript_slide(base)
    parsed = parse_powerpoint_context(base.active_file, visible_slide, base.selected_content)
    mismatch = applescript_slide != visible_slide if applescript_slide else False
    diagnostic = (
        f"visible_slide_from_screen: {visible_slide}\n"
        f"visible_slide_title_from_screen: {visible_title or parsed.title}\n"
        f"applescript_slide: {applescript_slide or 'unknown'}\n"
        f"slide_match: {'no' if mismatch else 'yes'}\n"
        f"screen_evidence:\n{screen_text[:1400]}"
    )
    return ActiveContext(
        app=base.app,
        selection_type="powerpoint_visible_slide",
        selected_content=base.selected_content,
        active_file=base.active_file,
        active_title=parsed.title,
        nearby_context=diagnostic,
        document_context=parsed.document_context,
        limits=parsed.limits + " Screen visible slide wins if PowerPoint scripting disagrees.",
        source="powerpoint_screen_verified_pptx_parser",
        confidence=max(base.confidence, 0.86),
        untrusted_influence=base.untrusted_influence,
        injection_detected=base.injection_detected,
        untrusted_source=base.untrusted_source,
        untrusted_signals=base.untrusted_signals,
    )


def _visible_slide(screen_text: str, path: str) -> tuple[int, str]:
    number = _slide_number(screen_text)
    if number:
        return number, ""
    title_match = _title_match(screen_text, path)
    return title_match


def _slide_number(text: str) -> int:
    patterns = (
        r"\bslide\s+(\d+)\b",
        r"\bpage\s+(\d+)\b",
        r"\b(\d+)\s*/\s*\d+\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return int(match.group(1))
    return 0


def _title_match(text: str, path: str) -> tuple[int, str]:
    try:
        deck = Presentation(path)
    except Exception:
        return 0, ""
    lowered = text.lower()
    for idx, slide in enumerate(deck.slides, start=1):
        title = _slide_title(slide)
        if title and title.lower() in lowered:
            return idx, title
    return 0, ""


def _slide_title(slide) -> str:
    if slide.shapes.title and slide.shapes.title.text:
        return slide.shapes.title.text.strip()
    for shape in slide.shapes:
        text = getattr(shape, "text", "").strip()
        if text:
            return text.splitlines()[0]
    return ""


def _applescript_slide(context: ActiveContext) -> int:
    for text in (context.nearby_context, context.document_context):
        match = re.search(r"\b(?:slide|current_slide):\s*(\d+)\b", text, flags=re.I)
        if match:
            return int(match.group(1))
    return 0
