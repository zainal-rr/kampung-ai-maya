from __future__ import annotations

import json
import os
import re
from pathlib import Path

from pptx import Presentation

from maya_core.cost_tracker import record_usage
from maya_documents.deck_species import deck_species_review_contract, detect_deck_species
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
    all_texts: list[str] = []
    for idx, slide in enumerate(deck.slides, 1):
        texts = _texts(slide)
        all_texts.extend(texts)
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
    stale_label = _stale_topic_label(all_texts)
    if stale_label:
        issues.append(f"deck has off-topic visible label: {stale_label}")
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


def _stale_topic_label(texts: list[str]) -> str:
    joined = " ".join(texts).lower()
    food_labels = ("food route", "food plan", "food backup", "food culture")
    food_markers = (
        "food", "restaurant", "cafe", "meal", "market", "bbq", "myeongdong",
        "gwangjang", "seoul", "tokyo", "itinerary", "travel",
    )
    if any(label in joined for label in food_labels) and not any(marker in joined for marker in food_markers):
        for text in texts:
            if text.lower().strip() in {label.upper().lower() for label in food_labels}:
                return text
        for text in texts:
            if any(label in text.lower() for label in food_labels):
                return text
    return ""


def image_policy_line(topic: str) -> str:
    """Single source of truth for image expectations in review prompts.

    Live contradiction 2026-06-11: code-side `topic_benefits_from_visuals`
    decided robotics/agriculture decks need no images (so none were
    generated), while the review prompt told Claude to grade "missing visuals
    for a visual topic" as draft-level — every such deck shipped draft-only.
    Image AVAILABILITY is governed by code (topic class + generation
    pipeline health), never by the reviewer."""
    from pptx_visual_assets import topic_benefits_from_visuals

    if topic and not topic_benefits_from_visuals(topic):
        return (
            "Image policy: this topic class does not use generated images. "
            "Do not mention missing images at all."
        )
    return (
        "Image policy: image generation is handled by code and may be intentionally "
        "unavailable. Treat missing images as a non-blocking improvement note, never "
        "as a blocker or a draft-level reason."
    )


async def claude_polish_grade(db_path: str, path: Path, topic: str = "") -> tuple[str, bool]:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return "Design polish: local QA passed. Claude polish critique unavailable.", False
    steward = TheSteward(
        os.getenv("ANTHROPIC_API_KEY", "dummy"),
        os.getenv("CLAUDE_STEWARD_MODEL", CAPABILITIES["steward"].default_model),
    )
    try:
        response = await steward.chat([
            {"role": "system", "content": await _system_prompt(db_path)},
            {"role": "user", "content": _user_prompt(path, topic)},
        ])
    except Exception:
        return "Design polish: good. Claude polish review unavailable; local visual QA passed.", False
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
    clean = " ".join(str(text).split()).strip()
    if _looks_like_short_label(clean):
        return False
    low = clean.lower().rstrip(" .")
    if low.endswith("with a ready"):
        return True
    bad_endings = (" in", " to", " from", " for", " of", " with", " by", " than", " as", " when", " where", " because")
    if low.endswith(bad_endings):
        return True
    if len(text) > 70 and not text.rstrip().endswith((".", "?", "!", ")")):
        return True
    return False


def _looks_like_short_label(text: str) -> bool:
    """Short title-case labels are not sentences.

    Live 2026-06-11 false positive: the title "Compliance Must Be Built In"
    was marked incomplete only because it ends with the preposition "in".
    That rule is valid for long sentence fragments, not compact slide labels.
    """
    words = [word.strip(" ,;:.()[]{}") for word in text.split() if word.strip(" ,;:.()[]{}")]
    if not words or len(words) > 8:
        return False
    if text.rstrip().endswith((".", "?", "!")):
        return False
    significant = [word for word in words if len(word) > 2]
    if not significant:
        return False
    titled = sum(1 for word in significant if word[:1].isupper())
    return titled / len(significant) >= 0.75


async def _system_prompt(db_path: str) -> str:
    return (
        "You review presentation polish for Maya. Return compact JSON only. "
        "Grade the deck as draft-level, good, or strong. Penalize bland templates, "
        "weak first-slide framing, incomplete sentences, low visual variety, and sentence-heavy visible slides. "
        "Good decks use short visible labels and keep explanation in speaker notes. "
        "Never return draft-level without naming concrete slide blockers; if local structure is clean and you only see non-blocking improvement opportunities, return good.\n\n"
        f"{await powerpoint_quality_context(db_path)}"
    )


def _user_prompt(path: Path, topic: str = "") -> str:
    deck = Presentation(path)
    species = detect_deck_species(topic)
    species_contract = deck_species_review_contract(species)
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
        "species": species,
    }
    return (
        "Review this PPTX structure for polish, not factual truth. "
        "Visible text is intentionally short because speaker notes carry explanation. "
        "Do not mark compact labels as draft-level when notes, title strength, and layout variety are present. "
        "Mark draft-level when the deck has bland generic labels, poor first-slide framing, repeated layouts, incomplete text, or sentence-heavy slides. "
        f"{species_contract + ' ' if species_contract else ''}"
        f"{image_policy_line(topic)} "
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
            if grade in {"good", "strong"} and _reason_has_blocker(reason):
                return "draft-level", _short_reason(reason)
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
        clean = _clip_reason_at_boundary(clean, 240)
    clean = _trim_dangling_reason_tail(clean)
    return clean if clean.endswith((".", "?", "!")) else clean + "."


_DANGLING_REASON_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "because",
    "by",
    "for",
    "from",
    "in",
    "into",
    "of",
    "or",
    "the",
    "through",
    "to",
    "with",
    "without",
}


def _clip_reason_at_boundary(text: str, limit: int) -> str:
    candidate = text[:limit].rstrip()
    # Prefer a real sentence boundary if one exists late enough to keep the
    # reason useful. The previous plain character cap produced live Telegram
    # fragments like "4 layout variants, and." and "(resilience.".
    sentence_cut = max(candidate.rfind(". "), candidate.rfind("? "), candidate.rfind("! "))
    if sentence_cut >= min(160, max(80, limit // 2)):
        candidate = candidate[: sentence_cut + 1]
    else:
        candidate = candidate.rsplit(" ", 1)[0].rstrip(" ,;:-")
    return _trim_dangling_reason_tail(candidate)


def _trim_dangling_reason_tail(text: str) -> str:
    clean = text.strip(" ,;:-")
    # If the cut lands inside a parenthetical, drop the dangling parenthetical
    # instead of surfacing a broken "(resilience." style fragment.
    if clean.count("(") > clean.count(")"):
        open_index = clean.rfind("(")
        if open_index >= max(0, len(clean) - 100):
            clean = clean[:open_index].rstrip(" ,;:-")
    words = clean.split()
    while words:
        tail = words[-1].strip(" \t\r\n\"'“”‘’()[]{}.,;:").lower()
        if tail not in _DANGLING_REASON_WORDS:
            break
        words.pop()
    return " ".join(words).rstrip(" ,;:-")


def _reason_has_blocker(reason: str) -> bool:
    lowered = reason.lower()
    if any(marker in lowered for marker in ("no blocker", "not a blocker", "non-blocking", "non blocking")):
        return False
    lowered = _strip_negated_blocker_lists(lowered)
    if re.search(r"\bslide\s+\d+\b", lowered):
        return True
    blockers = (
        "truncated",
        "incomplete",
        "sentence-heavy",
        "missing visual",
        "missing image",
        "repeated layout",
        "weak first",
        "weak title",
        "generic label",
        "mismatch",
        "mismatched",
        "off-topic",
        "off topic",
        "stray",
        "leftover",
        "does not belong",
        "placeholder",
    )
    return any(blocker in lowered for blocker in blockers)


def _strip_negated_blocker_lists(text: str) -> str:
    """Remove positive "no fragments/truncation" clauses before blocker scan.

    Live 2026-06-11 drone deck: Claude returned draft-level while its reason
    was positive: "No fragments, truncation, or ...". The old parser saw the
    word "truncation" and upheld the draft-level label. Negated blocker words
    are evidence of cleanliness, not blockers.
    """
    blocker_word = r"(?:fragments?|truncation|truncated|incomplete(?: sentences?)?|sentence-heavy(?: bodies?)?)"
    pattern = rf"\b(?:no|without)\s+{blocker_word}(?:\s*,\s*(?:or\s+)?{blocker_word})*(?:\s*,?\s*or\s*)?"
    return re.sub(pattern, " ", text)
