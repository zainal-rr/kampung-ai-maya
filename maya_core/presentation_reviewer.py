from __future__ import annotations

import json
import os
import re

from maya_core.cost_tracker import record_usage
from maya_documents.deck_species import deck_species_review_contract, detect_deck_species
from maya_documents.office_drafter_powerpoint import MAX_POWERPOINT_SLIDES
from maya_core.models import TheSteward
from maya_core.powerpoint_quality_context import powerpoint_quality_context
from maya_core.provider_capabilities import CAPABILITIES

Slides = list[tuple[str, list[str]]]


async def review_presentation_slides(db_path: str, topic: str, slides: Slides) -> Slides:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return slides
    steward = TheSteward(
        os.getenv("ANTHROPIC_API_KEY", "dummy"),
        os.getenv("CLAUDE_STEWARD_MODEL", CAPABILITIES["steward"].default_model),
    )
    try:
        response = await steward.chat([
            {"role": "system", "content": await _system_prompt(db_path)},
            {"role": "user", "content": _user_prompt(topic, slides)},
        ])
    except Exception:
        return slides
    reviewed = _parse_slides(response)
    if reviewed:
        await record_usage(db_path, "claude_steward_calls", 1, "presentation review")
        return reviewed[:MAX_POWERPOINT_SLIDES]
    return slides


async def _system_prompt(db_path: str) -> str:
    return (
        "You are Maya's Claude presentation designer and deck editor. Gemini already drafted "
        "the role-based content and key points. Preserve that factual content, but improve the "
        "story arc, slide titles, executive usefulness, visual rhythm, and scannability. Convert "
        "dense facts into clear slide messages without inventing unsupported claims. Return only valid JSON."
        "\n\n"
        f"{await powerpoint_quality_context(db_path)}"
    )


def _user_prompt(topic: str, slides: Slides) -> str:
    payload = [{"title": title, "bullets": bullets[:5]} for title, bullets in slides]
    species_contract = deck_species_review_contract(detect_deck_species(topic))
    return (
        f"Topic: {topic}\n\n"
        "Rewrite this as a cleaner, better-designed draft deck. Do not force a fixed slide count; use as many slides as the topic needs while keeping the story focused. "
        "Each slide title should provide a clear visual cue or point. "
        "Each slide should carry enough concrete support to be useful; Maya's builder will keep visible text readable and move overflow explanation into speaker notes. "
        "Avoid generic bullets, crowded text, sentence-heavy visible slides, and unsupported certainty. "
        "Use the Gemini content as the factual source. Improve design, structure, pacing, and slide language. "
        "Use a practical flow: context, sharp point of view, key decisions, tradeoffs, and what to do next. "
        f"{species_contract + ' ' if species_contract else ''}"
        "Return JSON only in this shape: "
        '[{"title":"Slide title","bullets":["bullet one","bullet two"]}]\n\n'
        f"Current slides:\n{json.dumps(payload, ensure_ascii=False)}"
    )


def _parse_slides(text: str) -> Slides:
    raw = _json_blob(text)
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    slides: Slides = []
    if not isinstance(data, list):
        return []
    for item in data:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        bullets = item.get("bullets", [])
        if not title or not isinstance(bullets, list):
            continue
        clean_bullets = [str(bullet).strip() for bullet in bullets if str(bullet).strip()]
        if clean_bullets:
            slides.append((title, clean_bullets[:4]))
    return slides


def _json_blob(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    match = re.search(r"\[[\s\S]*\]", cleaned)
    return match.group(0) if match else ""
