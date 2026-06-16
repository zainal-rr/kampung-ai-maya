"""PowerPoint creation QA loop.

The caller gives this module a title and slide outline. This flow builds the
editable PPTX locally, runs visual/text QA, optionally rebuilds the deck through
topic-safe repair, inserts Gemini visual assets when the topic benefits from
images, checks image count/fit through the rendered deck inspector, and records
the artifact review for `/review`.

Keep generation and proof separate: Gemini/Claude can influence content and
polish, but the file is only deliverable when local PPTX inspection and the
review gate agree that the deck is usable.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from maya_documents.artifact_review_store import record_artifact_review
from maya_harness.harness_artifact_store import record_structured_artifact
from maya_harness.harness_models import local_artifact
from pptx_polish_review import claude_polish_grade, local_polish_issues
from office_modern_files import create_pptx
from pptx import Presentation
from pptx_quality_gate import inspect_pptx_quality, PptxQualityResult
from pptx_topic_reviser import rebuild_topic_safe
from pptx_visual_assets import add_gemini_visual_asset, required_visual_image_count, topic_benefits_from_visuals
from pptx_slide_repair import attempt_slides, max_pptx_attempts
from provider_capabilities import CAPABILITIES
from storage import upsert_preference


async def create_powerpoint_with_qa(
    db_path: str,
    path: Path,
    title: str,
    slides: list[tuple[str, list[str]]],
    run_id: str,
    last_doc_key: str,
    auto_improve: bool = True,
    visual_image_max: int | None = None,
) -> PptxQualityResult:
    slides = _normalize_slides(title, slides)
    attempts = max_pptx_attempts(auto_improve)
    qa = PptxQualityResult(False, ["PowerPoint QA did not run"], [], 0, "")
    visual_note = ""
    for attempt in range(attempts):
        qa, visual_note = await _run_powerpoint_attempt(db_path, path, title, attempt_slides(slides, attempt, title), run_id, auto_improve, visual_image_max)
        qa.revisions = attempt
        if qa.passed:
            break
        if not auto_improve:
            break
    if qa.passed:
        await upsert_preference(db_path, last_doc_key, str(path), source="document")
    await record_artifact_review(
        db_path,
        "pptx",
        title,
        _reviewer_model(),
        qa.passed,
        _artifact_review_text(qa, visual_note),
    )
    await record_structured_artifact(
        db_path,
        run_id,
        local_artifact("presentation", str(path), f"PowerPoint QA: {qa.summary()} {visual_note}", "document_actions"),
    )
    return qa


async def _run_powerpoint_attempt(
    db_path: str,
    path: Path,
    title: str,
    slides: list[tuple[str, list[str]]],
    run_id: str,
    auto_improve: bool,
    visual_image_max: int | None,
) -> tuple[PptxQualityResult, str]:
    return await _run_powerpoint_attempt_impl(db_path, path, title, slides, run_id, auto_improve, visual_image_max)


def _qa_note(qa: PptxQualityResult, text: str) -> None:
    qa.notes = [*(qa.notes or []), text]


def _append_sentence(text: str, note: str) -> str:
    clean = " ".join(str(text or "").split()).strip()
    clean_note = " ".join(str(note or "").split()).strip()
    if not clean:
        return clean_note
    if not clean_note:
        return clean
    separator = " " if clean.endswith((".", "?", "!")) else ". "
    return f"{clean}{separator}{clean_note}"


def _visual_budget_seconds() -> float:
    try:
        return float(os.getenv("MAYA_PPTX_VISUAL_BUDGET_SECONDS", "120"))
    except ValueError:
        return 120.0


async def _polish_grade_with_topic(db_path: str, path, title: str):
    """Call claude_polish_grade with the topic when its signature supports it.
    Smoke fakes patch claude_polish_grade with (db_path, path) signatures, so
    introspect instead of breaking them (same pattern as _draft_markdown)."""
    import inspect as _inspect

    try:
        signature = _inspect.signature(claude_polish_grade)
        supports_topic = "topic" in signature.parameters or len(signature.parameters) >= 3
    except (TypeError, ValueError):
        supports_topic = False
    if supports_topic:
        return await claude_polish_grade(db_path, path, topic=title)
    return await claude_polish_grade(db_path, path)


async def _run_powerpoint_attempt_impl(
    db_path: str,
    path,
    title: str,
    slides: list[tuple[str, list[str]]],
    run_id: str,
    auto_improve: bool,
    visual_image_max: int | None,
) -> tuple[PptxQualityResult, str]:
    await asyncio.to_thread(create_pptx, path, title, slides)
    visual_added = False
    visual_note = ""
    qa = await asyncio.to_thread(inspect_pptx_quality, path)
    if auto_improve and not qa.passed:
        revised = await asyncio.to_thread(rebuild_topic_safe, path, slides)
        if revised.passed or len(revised.issues) < len(qa.issues):
            qa = revised
            qa.revisions = 1
    topic_issues = await asyncio.to_thread(_topic_fit_issues, title, path)
    if topic_issues:
        qa.passed = False
        qa.issues.extend(topic_issues)
    if auto_improve and qa.passed and local_polish_issues(path):
        qa = await asyncio.to_thread(rebuild_topic_safe, path, slides)
        qa.revisions = 1
    if qa.passed:
        # Wall-clock budget for the entire visual stage: live 2026-06-11 the
        # drone deck spent 313.9s in image generation/stalled writes. On
        # timeout the existing availability-note path takes over.
        visual_budget = _visual_budget_seconds()
        try:
            if visual_budget > 0:
                visual_added, visual_note = await asyncio.wait_for(
                    add_gemini_visual_asset(path, title, max_images=visual_image_max),
                    timeout=visual_budget,
                )
            else:
                visual_added, visual_note = await add_gemini_visual_asset(path, title, max_images=visual_image_max)
        except asyncio.TimeoutError:
            visual_added, visual_note = False, f"visual stage exceeded its {visual_budget:.0f}s budget"
        wants_visuals = topic_benefits_from_visuals(title)
        if visual_added:
            qa = await asyncio.to_thread(inspect_pptx_quality, path)
            picture_count = await asyncio.to_thread(_picture_count, path)
            required = required_visual_image_count(len(slides))
            if visual_image_max is not None:
                required = min(required, max(0, visual_image_max))
            if wants_visuals and picture_count < required:
                # Severity-tier rule (live 2026-06-11): image AVAILABILITY is
                # never a deck blocker. Fewer images than suggested = deliver
                # with an honest note, not draft-only.
                _qa_note(qa, f"visual topic got {picture_count} of {required} suggested images; delivered with available visuals")
        elif wants_visuals:
            # Live P3 failure shape: generation/insert infrastructure failed
            # (slow provider, stalled Desktop write, or disabled flag) after
            # 307s and the deck was blocked for it. The deck itself is fine.
            _qa_note(qa, f"visual assets unavailable ({visual_note or 'no image inserted'}); delivered without images")
        elif not visual_note:
            visual_note = "No generated visual asset inserted."
    else:
        visual_note = "Gemini visual asset skipped because text/layout QA did not pass."
    if qa.passed:
        issues = local_polish_issues(path)
        if issues:
            qa.passed = False
            qa.polish = "Design polish: draft-level."
            qa.issues.extend(issues)
        else:
            polish = (await _polish_grade_with_topic(db_path, path, title))[0]
            polish = polish.replace("draft level", "draft-level")
            if visual_added:
                polish = _append_sentence(polish, "Gemini visual asset added.")
            qa.polish = polish
            if _draft_level_polish(polish):
                qa.passed = False
                qa.issues.append("design polish remained draft-level")
            elif _polish_reason_contains_blocker(polish):
                qa.passed = False
                qa.issues.append("design polish still mentions blocking weak spots")
            await record_structured_artifact(
                db_path,
                run_id,
                local_artifact("presentation", str(path), polish, "pptx_polish_review"),
            )
    return qa, visual_note


def _reviewer_model() -> str:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return "local-pptx-qa"
    return os.getenv("CLAUDE_STEWARD_MODEL", CAPABILITIES["steward"].default_model)


def _topic_fit_issues(title: str, path: Path) -> list[str]:
    lowered_title = str(title).lower()
    deck = Presentation(path)
    text = " ".join(
        " ".join(getattr(shape, "text", "").split()).lower()
        for slide in deck.slides
        for shape in slide.shapes
    )
    required_groups = _topic_required_groups(lowered_title)
    if required_groups:
        hits = [
            marker
            for group in required_groups
            for marker in group
            if marker in text
        ]
        if len(set(hits)) < min(2, len(required_groups) + 1):
            return [f"deck content does not match requested topic: {title}"]
        return []
    if not any(word in lowered_title for word in ("office", "priority", "priorities", "weekly", "team")):
        return []
    office_markers = ("office", "weekly", "week", "priority", "priorities", "team", "owner", "deep work", "scorecard")
    technical_markers = ("router", "wifi", "wan", "lan", "dhcp", "dns", "admin password", "running config")
    if any(marker in text for marker in office_markers):
        return []
    if any(marker in text for marker in technical_markers):
        return ["deck content does not match weekly office priorities topic"]
    return ["deck content is too generic for weekly office priorities topic"]


def _topic_required_groups(lowered_title: str) -> list[tuple[str, ...]]:
    rules = (
        (("kampung ai",), [("kampung", "maya", "ai"), ("voice", "browser", "document", "memory"), ("safety", "provider", "routing", "tools")]),
        (("youtube learning", "youtube strategy", "video scoring"), [("youtube", "video", "channel"), ("views", "scoring", "subscribed", "creator"), ("notes", "practice", "summary")]),
        (("drone", "uav", "aerial"), [("drone", "uav", "aerial"), ("inspection", "flight", "pilot", "payload"), ("compliance", "safety", "equipment", "pricing")]),
        (("agriculture", "crop", "fertilizer"), [("agriculture", "crop", "farm"), ("climate", "water", "fertilizer", "labor"), ("policy", "mitigation", "recommendation")]),
        (("almaty", "kazakhstan", "hiking"), [("almaty", "kazakhstan"), ("hiking", "mountain", "trail"), ("budget", "packing", "safety", "itinerary")]),
        (("japan", "osaka", "kyoto"), [("japan", "osaka", "kyoto"), ("flight", "hotel", "airbnb"), ("budget", "decision", "workflow")]),
        (("browser", "google search", "youtube", "reddit"), [("browser", "search", "google"), ("youtube", "reddit", "images", "flights"), ("safety", "automation", "route")]),
        (("google cloud", "cloud cost"), [("cloud", "google"), ("budget", "cost", "alert"), ("security", "logging", "monitoring")]),
        (("robotics", "workshop"), [("robotics", "workshop"), ("kits", "team", "judging"), ("learning", "agenda", "assessment")]),
        (("modern kampung", "house design"), [("kampung", "house"), ("materials", "layout", "climate"), ("cost", "design", "build")]),
    )
    for markers, groups in rules:
        if any(marker in lowered_title for marker in markers):
            return groups
    return []


def _artifact_review_text(qa: PptxQualityResult, visual_note: str) -> str:
    if qa.passed:
        rendered = len(qa.images)
        return (
            "PASS: PowerPoint visual QA passed and the deck is deliverable.\n\n"
            "Checks confirmed:\n"
            f"- Rendered slides: {rendered}.\n"
            "- The deck opens as a real editable `.pptx` file.\n"
            "- No placeholder phrases, ellipsis overflow, repeated weak titles, sentence-heavy visible slides, or local truncation issues blocked delivery.\n"
            "- Explanatory detail is kept in speaker notes so slides can stay visual and concise.\n"
            f"- Polish result: {qa.polish or 'local structure passed'}\n"
            f"- Visual asset status: {visual_note}"
        )
    return (
        "REJECT: PowerPoint visual QA did not pass, so the deck should remain a draft.\n\n"
        "Blocking issues:\n"
        + "\n".join(f"- {issue}" for issue in qa.issues[:8])
        + f"\n\nVisual asset status: {visual_note}"
    )


def _draft_level_polish(polish: str) -> bool:
    lowered = polish.lower()
    return "draft-level" in lowered or "draft level" in lowered


def _polish_reason_contains_blocker(polish: str) -> bool:
    lowered = polish.lower()
    blockers = (
        "incomplete fragment",
        "incomplete fragments",
        "incomplete sentence",
        "incomplete sentences",
        "held back from strong by incomplete",
        "weak spot",
        "weak spots",
        "mismatch",
        "mismatched",
        "off-topic",
        "off topic",
        "leftover",
        "stray",
        "does not belong",
        "truncated",
        "fragment like",
        "fragments like",
        "a couple of",
    )
    return any(blocker in lowered for blocker in blockers)


def _normalize_slides(title: str, slides: list[tuple[str, list[str]]]) -> list[tuple[str, list[str]]]:
    if not slides:
        return [(title, ["Use this deck to make the topic clear and actionable."])]
    normalized = list(slides)
    first_title, first_bullets = normalized[0]
    if len(str(first_title).strip()) < 8 or len(str(first_title).split()) < 2:
        normalized[0] = (title, first_bullets)
    return normalized


def _picture_count(path: Path) -> int:
    deck = Presentation(path)
    return sum(1 for slide in deck.slides for shape in slide.shapes if getattr(shape, "shape_type", None) == 13)
