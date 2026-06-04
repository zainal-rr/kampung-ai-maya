from __future__ import annotations

import json
import os
import re
from pathlib import Path

from pptx import Presentation

from cost_tracker import record_usage
from models import TheSteward
from powerpoint_quality_context import powerpoint_quality_context
from provider_capabilities import CAPABILITIES


def local_polish_issues(path: Path) -> list[str]:
    deck = Presentation(path)
    issues: list[str] = []
    titles: list[str] = []
    repeated_layouts = 0
    signatures: list[tuple[tuple[int, int, int, int], ...]] = []
    last_signature = None
    for idx, slide in enumerate(deck.slides, 1):
        texts = _texts(slide)
        if not texts:
            continue
        bad_text = _bad_visible_text(texts)
        if bad_text:
            issues.append(f"slide {idx} has weak visible label: {bad_text}")
        titles.append(_title_text(texts))
        if any(_incomplete_sentence(text) for text in texts):
            issues.append(f"slide {idx} has an incomplete sentence")
        signature = _layout_signature(slide)
        signatures.append(signature)
        if signature == last_signature:
            repeated_layouts += 1
        last_signature = signature
    if len(set(titles)) < len(titles):
        issues.append("deck repeats slide titles")
    if len(signatures) >= 5 and len(set(signatures)) < 3:
        issues.append("deck uses too little layout variety")
    if repeated_layouts >= max(3, len(titles) - 2):
        issues.append("deck uses too little layout variety")
    return issues


BAD_VISIBLE_LABELS = (
    "slide focus",
    "key move",
    "weekend food tour built",
    "avoid building the day",
    "visual presentation",
    "hit gwangjang market: 30",
)


def _bad_visible_text(texts: list[str]) -> str:
    for text in texts:
        lowered = text.lower().strip()
        if lowered == "leave with a ready":
            return text
        if any(label in lowered for label in BAD_VISIBLE_LABELS):
            return text
        if lowered.endswith(" built"):
            return text
    return ""


async def claude_polish_grade(db_path: str, path: Path) -> tuple[str, bool]:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return "Design polish: local QA passed. Claude polish critique unavailable.", False
    steward = TheSteward(
        os.getenv("ANTHROPIC_API_KEY", "dummy"),
        os.getenv("CLAUDE_STEWARD_MODEL", CAPABILITIES["steward"].default_model),
    )
    response = await steward.chat([
        {"role": "system", "content": await _system_prompt(db_path)},
        {"role": "user", "content": _user_prompt(path)},
    ])
    await record_usage(db_path, "claude_steward_calls", 1, "pptx polish review")
    grade, reason = _parse_polish(response)
    suffix = f" {reason}" if reason else ""
    return f"Design polish: {grade}.{suffix}", True


def _texts(slide) -> list[str]:
    items = []
    for shape in slide.shapes:
        text = " ".join(getattr(shape, "text", "").split())
        if text:
            items.append(text)
    return items


def _title_text(texts: list[str]) -> str:
    for text in texts:
        clean = text.strip()
        if not clean:
            continue
        if clean.isupper() and len(clean.split()) <= 3:
            continue
        if len(clean.split()) >= 3 or len(clean) >= 24:
            return clean
    return texts[0] if texts else ""


def _layout_signature(slide) -> tuple[tuple[int, int, int, int], ...]:
    boxes: list[tuple[int, int, int, int]] = []
    for shape in slide.shapes:
        text = " ".join(getattr(shape, "text", "").split())
        if not text:
            continue
        boxes.append((
            round(int(shape.left) / 100000),
            round(int(shape.top) / 100000),
            round(int(shape.width) / 100000),
            round(int(shape.height) / 100000),
        ))
    return tuple(boxes[:10])


def _incomplete_sentence(text: str) -> bool:
    low = text.lower().rstrip(" .")
    if low.endswith("with a ready"):
        return True
    bad_endings = (" in", " to", " from", " for", " of", " with", " by", " than", " as", " when", " where", " because")
    if low.endswith(bad_endings):
        return True
    if len(text) > 70 and not text.rstrip().endswith((".", "?", "!", ")")):
        return True
    return False


async def _system_prompt(db_path: str) -> str:
    return (
        "You review presentation polish for Maya. Return compact JSON only. "
        "Grade the deck as draft-level, good, or strong. Penalize bland templates, "
        "weak first-slide framing, incomplete sentences, low visual variety, and sentence-heavy visible slides. "
        "Good decks use short visible labels and keep explanation in speaker notes. "
        "Never return draft-level without naming concrete slide blockers; if local structure is clean and you only see non-blocking improvement opportunities, return good.\n\n"
        f"{await powerpoint_quality_context(db_path)}"
    )


def _user_prompt(path: Path) -> str:
    deck = Presentation(path)
    slides = []
    picture_total = 0
    note_total = 0
    for idx, slide in enumerate(deck.slides, 1):
        texts = _texts(slide)
        picture_count = sum(1 for shape in slide.shapes if getattr(shape, "shape_type", None) == 13)
        picture_total += picture_count
        notes = _notes_text(slide)
        if notes:
            note_total += 1
        slides.append({"slide": idx, "texts": texts[:8], "pictures": picture_count, "has_notes": bool(notes)})
    local_summary = {
        "slides": len(deck.slides),
        "pictures": picture_total,
        "slides_with_notes": note_total,
        "layout_variants": len({_layout_signature(slide) for slide in deck.slides}),
        "theme_background": str(deck.slides[0].background.fill.fore_color.rgb) if deck.slides else "",
    }
    return (
        "Review this PPTX structure for polish, not factual truth. "
        "Visible text is intentionally short because speaker notes carry explanation. "
        "Do not mark compact labels as draft-level when images, notes, title strength, and layout variety are present. "
        "Mark draft-level when the deck has bland generic labels, poor first-slide framing, missing visuals for a visual topic, repeated layouts, incomplete text, or sentence-heavy slides. "
        "If your reason mentions incomplete fragments, incomplete sentences, weak spots, truncation, or similar blockers, the grade must be draft-level. "
        'Return {"grade":"draft-level|good|strong","reason":"short reason"}.\n\n'
        f"Local summary:\n{json.dumps(local_summary, ensure_ascii=False)}\n\n"
        f"Slides:\n{json.dumps(slides, ensure_ascii=False)}"
    )


def _notes_text(slide) -> str:
    try:
        return " ".join(slide.notes_slide.notes_text_frame.text.split())
    except Exception:
        return ""


def _parse_polish(text: str) -> tuple[str, str]:
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            data = json.loads(match.group(0))
            grade = str(data.get("grade", "")).strip().lower()
            reason = str(data.get("reason", "")).strip()
            if grade == "draft-level" and not reason:
                return "good", "Local QA found no blocker, and Claude returned no actionable draft-level reason."
            if grade == "draft-level" and not _reason_has_blocker(reason):
                return "good", f"Local QA found no blocker; Claude critique was non-blocking: {_short_reason(reason)}"
            if grade in {"draft-level", "good", "strong"}:
                return grade, _short_reason(reason)
        except json.JSONDecodeError:
            pass
    lowered = text.lower()
    if "strong" in lowered:
        return "strong", ""
    if "good" in lowered:
        return "good", ""
    return "good", "Local QA found no blocker, and Claude returned no actionable draft-level reason."


def _short_reason(reason: str) -> str:
    clean = " ".join(reason.split()).strip()
    if not clean:
        return ""
    if len(clean) > 240:
        clean = clean[:240].rsplit(" ", 1)[0].rstrip(" ,;:-") + "."
    return clean if clean.endswith((".", "?", "!")) else clean + "."


def _reason_has_blocker(reason: str) -> bool:
    lowered = reason.lower()
    blockers = (
        "slide ",
        "truncated",
        "incomplete",
        "sentence-heavy",
        "missing visual",
        "missing image",
        "repeated layout",
        "weak first",
        "weak title",
        "generic label",
        "placeholder",
    )
    return any(blocker in lowered for blocker in blockers)
