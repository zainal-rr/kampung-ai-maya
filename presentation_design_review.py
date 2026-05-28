from __future__ import annotations

import os
import re
from pathlib import Path

from cost_tracker import record_usage
from artifact_quality import artifact_skill_context
from models import TheSenses, TheSteward
from pptx_slide_renderer import render_pptx_slides
from office_modern_files import safe_slug
from provider_capabilities import CAPABILITIES
from skill_store import find_skill
from workspace_paths import workspace_dir


def wants_presentation_review(text: str) -> bool:
    low = text.lower()
    return any(word in low for word in ("review", "critique", "check")) and any(
        word in low for word in ("presentation", "ppt", "pptx", "slides", "deck")
    )


async def review_presentation_design(db_path: str, text: str) -> tuple[str, bool]:
    path = _find_presentation(text)
    if path is None:
        return "I could not find the presentation file in Desktop/Maya/presentations yet.", False
    summary = _inspect_pptx(path)
    visual_notes, visual_cost = await _visual_notes(db_path, path, text)
    if not os.getenv("ANTHROPIC_API_KEY"):
        return _local_review(path, summary, visual_notes), visual_cost
    skill_context = await _design_skill_context(db_path)
    steward = TheSteward(
        os.getenv("ANTHROPIC_API_KEY", "dummy"),
        os.getenv("CLAUDE_STEWARD_MODEL", CAPABILITIES["steward"].default_model),
    )
    reply = await steward.chat([
        {"role": "system", "content": _system_prompt(skill_context)},
        {"role": "user", "content": f"Request: {text}\n\nFile: {path}\n\nDeck inspection:\n{summary}\n\nVisual notes:\n{visual_notes or 'No visual notes available.'}"},
    ])
    await record_usage(db_path, "claude_steward_calls", 1, "presentation design review")
    return _clean_reply(path, reply, bool(visual_notes)), True


def _find_presentation(text: str) -> Path | None:
    root = workspace_dir("presentations")
    topic = _topic_from_review_request(text)
    candidates = sorted(root.glob("*.pptx"), key=lambda item: item.stat().st_mtime, reverse=True)
    if topic:
        slug = safe_slug(topic)
        for path in candidates:
            if path.stem == slug or slug in path.stem:
                return path
        tokens = {token for token in slug.split("-") if len(token) > 2}
        scored = [
            (sum(1 for token in tokens if token in path.stem), path)
            for path in candidates
        ]
        scored = [item for item in scored if item[0] > 0]
        if scored:
            return sorted(scored, key=lambda item: item[0], reverse=True)[0][1]
    return candidates[0] if candidates else None


def _topic_from_review_request(text: str) -> str:
    cleaned = re.sub(r"\b(review|critique|check|the|my|presentation|pptx?|slides?|deck|design)\b", " ", text, flags=re.I)
    return " ".join(cleaned.split())


def _inspect_pptx(path: Path) -> str:
    from pptx import Presentation

    deck = Presentation(path)
    lines = [f"slides: {len(deck.slides)}"]
    for idx, slide in enumerate(deck.slides, 1):
        texts = []
        shape_count = len(slide.shapes)
        image_count = sum(1 for shape in slide.shapes if getattr(shape, "shape_type", None) == 13)
        for shape in slide.shapes:
            text = getattr(shape, "text", "").strip()
            if text:
                texts.append(" ".join(text.split()))
        title = texts[0] if texts else "Untitled"
        body = " | ".join(texts[1:4])
        lines.append(f"{idx}) {title} shapes={shape_count} images={image_count} body={body[:280]}")
    return "\n".join(lines)


async def _visual_notes(db_path: str, path: Path, request: str) -> tuple[str, bool]:
    if not os.getenv("GOOGLE_API_KEY"):
        return "", False
    out_dir = workspace_dir("screenshots", create=True) / "pptx-reviews" / path.stem
    images = render_pptx_slides(path, out_dir, limit=8)
    if not images:
        return "", False
    senses = TheSenses(os.getenv("GOOGLE_API_KEY", "dummy"))
    notes = []
    for idx, image in enumerate(images, 1):
        prompt = (
            "You are Maya's slide vision reviewer. Inspect the rendered slide image for actual visual layout. "
            "Comment on hierarchy, spacing, density, alignment, contrast, visual polish, and obvious truncation. "
            "Be concise and do not mention provider names. "
            f"User request: {request}. Slide {idx}."
        )
        try:
            note = await senses.describe_image(image.read_bytes(), prompt)
        except Exception as exc:
            notes.append(f"{idx}) Vision review failed: {exc}")
            continue
        notes.append(f"{idx}) {note.strip()[:900]}")
    await record_usage(db_path, "gemini_vision_calls", len(images), "pptx slide visual review")
    return "\n".join(notes), True


async def _design_skill_context(db_path: str) -> str:
    skill = await find_skill(db_path, "Design Engineering")
    path = Path(str(skill.get("scaffold_path") or "")) if skill else None
    if not path or not path.exists():
        return ""
    text = path.read_text("utf-8", errors="ignore")
    return (artifact_skill_context("pptx") + "\n\n" + text)[:5500]


def _system_prompt(skill_context: str) -> str:
    return (
        "You are Maya reviewing a PowerPoint design directly from its PPTX structure. "
        "Use Design Engineering taste principles if provided. Be practical, concise, and honest. "
        "Do not ask Zainal to export slides manually. Review actual visual notes when provided, "
        "plus layout, story, density, hierarchy, visual polish, and next fixes. Avoid emojis and exclamation marks. "
        "If visual notes are missing, say the review is based on structure and text only.\n\n"
        f"Design skill context:\n{skill_context or 'No active design skill context.'}"
    )


def _local_review(path: Path, summary: str, visual_notes: str) -> str:
    visual = f"\n\nVisual notes from rendered slides:\n{visual_notes}" if visual_notes else "\n\nNo visual rendering notes available."
    return f"I reviewed the deck at {path}.\n\nDeck structure:\n{summary}{visual}"


def _clean_reply(path: Path, reply: str, has_visual_notes: bool) -> str:
    body = reply.strip() or "I reviewed the deck, but the review came back empty."
    mode = "including rendered slide visuals" if has_visual_notes else "from structure and text only"
    return f"I reviewed the PPTX directly {mode}: {path}\n\n{body}"
