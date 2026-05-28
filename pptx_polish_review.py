from __future__ import annotations

import json
import os
import re
from pathlib import Path

from pptx import Presentation

from artifact_quality import artifact_skill_context
from cost_tracker import record_usage
from models import TheSteward
from provider_capabilities import CAPABILITIES


def local_polish_issues(path: Path) -> list[str]:
    deck = Presentation(path)
    issues: list[str] = []
    titles: list[str] = []
    repeated_layouts = 0
    last_count = None
    for idx, slide in enumerate(deck.slides, 1):
        texts = _texts(slide)
        if not texts:
            continue
        titles.append(texts[0])
        if any(_incomplete_sentence(text) for text in texts):
            issues.append(f"slide {idx} has an incomplete sentence")
        count = len(texts)
        if count == last_count:
            repeated_layouts += 1
        last_count = count
    if len(set(titles)) < len(titles):
        issues.append("deck repeats slide titles")
    if repeated_layouts >= max(3, len(titles) - 2):
        issues.append("deck uses too little layout variety")
    return issues


async def claude_polish_grade(db_path: str, path: Path) -> tuple[str, bool]:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return "Design polish: draft-level. Claude polish critique unavailable.", False
    steward = TheSteward(
        os.getenv("ANTHROPIC_API_KEY", "dummy"),
        os.getenv("CLAUDE_STEWARD_MODEL", CAPABILITIES["steward"].default_model),
    )
    response = await steward.chat([
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": _user_prompt(path)},
    ])
    await record_usage(db_path, "claude_steward_calls", 1, "pptx polish review")
    grade = _parse_grade(response)
    return f"Design polish: {grade}.", True


def _texts(slide) -> list[str]:
    items = []
    for shape in slide.shapes:
        text = " ".join(getattr(shape, "text", "").split())
        if text:
            items.append(text)
    return items


def _incomplete_sentence(text: str) -> bool:
    low = text.lower().rstrip(" .")
    bad_endings = (" in", " to", " from", " for", " of", " with", " by", " than", " as")
    if low.endswith(bad_endings):
        return True
    if len(text) > 70 and not text.rstrip().endswith((".", "?", "!", ")")):
        return True
    return False


def _system_prompt() -> str:
    return (
        "You review presentation polish for Maya. Return compact JSON only. "
        "Grade the deck as draft-level, good, or strong. Penalize bland templates, "
        "weak first-slide framing, incomplete sentences, and low visual variety.\n\n"
        f"PowerPoint artifact quality skill:\n{artifact_skill_context('pptx')}"
    )


def _user_prompt(path: Path) -> str:
    deck = Presentation(path)
    slides = []
    for idx, slide in enumerate(deck.slides, 1):
        texts = _texts(slide)
        slides.append({"slide": idx, "texts": texts[:8]})
    return (
        "Review this PPTX structure for polish, not factual truth. "
        'Return {"grade":"draft-level|good|strong","reason":"short reason"}.\n\n'
        f"{json.dumps(slides, ensure_ascii=False)}"
    )


def _parse_grade(text: str) -> str:
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            grade = str(json.loads(match.group(0)).get("grade", "")).strip().lower()
            if grade in {"draft-level", "good", "strong"}:
                return grade
        except json.JSONDecodeError:
            pass
    lowered = text.lower()
    if "strong" in lowered:
        return "strong"
    if "good" in lowered:
        return "good"
    return "draft-level"
