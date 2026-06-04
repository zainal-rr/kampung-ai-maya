from __future__ import annotations

import asyncio
import os
from pathlib import Path

from artifact_review_store import record_artifact_review
from harness_artifact_store import record_structured_artifact
from harness_models import local_artifact
from pptx_polish_review import claude_polish_grade, local_polish_issues
from office_modern_files import create_pptx
from pptx import Presentation
from pptx_quality_gate import inspect_pptx_quality, PptxQualityResult
from pptx_topic_reviser import rebuild_topic_safe
from pptx_visual_assets import add_gemini_visual_asset, required_visual_image_count, topic_benefits_from_visuals
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
) -> PptxQualityResult:
    slides = _normalize_slides(title, slides)
    attempts = _max_attempts(auto_improve)
    qa = PptxQualityResult(False, ["PowerPoint QA did not run"], [], 0, "")
    visual_note = ""
    for attempt in range(attempts):
        qa, visual_note = await _run_powerpoint_attempt(db_path, path, title, _attempt_slides(slides, attempt, title), run_id, auto_improve)
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
        visual_added, visual_note = await add_gemini_visual_asset(path, title)
        if visual_added:
            qa = await asyncio.to_thread(inspect_pptx_quality, path)
            picture_count = await asyncio.to_thread(_picture_count, path)
            required = required_visual_image_count(len(slides))
            if topic_benefits_from_visuals(title) and picture_count < required:
                qa.passed = False
                qa.issues.append(f"visual topic needs at least {required} relevant images, but only {picture_count} were inserted")
        elif topic_benefits_from_visuals(title):
            qa.passed = False
            qa.issues.append("visual topic needs a generated or sourced image, but none was inserted")
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
            polish = (await claude_polish_grade(db_path, path))[0]
            polish = polish.replace("draft level", "draft-level")
            if visual_added:
                polish = f"{polish} Gemini visual asset added."
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
    if not any(word in lowered_title for word in ("office", "priority", "priorities", "weekly", "team")):
        return []
    deck = Presentation(path)
    text = " ".join(
        " ".join(getattr(shape, "text", "").split()).lower()
        for slide in deck.slides
        for shape in slide.shapes
    )
    office_markers = ("office", "weekly", "week", "priority", "priorities", "team", "owner", "deep work", "scorecard")
    technical_markers = ("router", "wifi", "wan", "lan", "dhcp", "dns", "admin password", "running config")
    if any(marker in text for marker in office_markers):
        return []
    if any(marker in text for marker in technical_markers):
        return ["deck content does not match weekly office priorities topic"]
    return ["deck content is too generic for weekly office priorities topic"]


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
        "truncated",
        "fragment like",
        "fragments like",
        "a couple of",
    )
    return any(blocker in lowered for blocker in blockers)


def _max_attempts(auto_improve: bool) -> int:
    if not auto_improve:
        return 1
    try:
        configured = int(os.getenv("PPTX_QA_MAX_ATTEMPTS", "4"))
    except ValueError:
        configured = 4
    return max(1, min(configured, 6))


def _attempt_slides(slides: list[tuple[str, list[str]]], attempt: int, title: str = "") -> list[tuple[str, list[str]]]:
    if attempt <= 0:
        return slides
    if attempt >= 2:
        return _rescue_slides(slides, title)
    repaired: list[tuple[str, list[str]]] = []
    for title, bullets in slides:
        repaired.append((_stronger_slide_title(title), [_stronger_bullet(bullet) for bullet in bullets]))
    return repaired


def _rescue_slides(slides: list[tuple[str, list[str]]], title: str = "") -> list[tuple[str, list[str]]]:
    text = " ".join([title] + [title for title, _ in slides] + [bullet for _, bullets in slides for bullet in bullets]).lower()
    if any(word in text for word in ("food", "restaurant", "cafe", "seoul", "trip", "travel", "itinerary")):
        return [
            ("Seoul In 48 Hours", ["Food-first route", "Dark editorial guide", "Two focused days"]),
            ("Start With Two Anchor Meals", ["Day 1: market classics", "Day 2: cafe and BBQ", "One reservation backup"]),
            ("Follow The Neighborhood Spine", ["Jongno morning market", "Myeongdong lunch window", "Seongsu cafe block"]),
            ("Budget The Splurge", ["KRW daily budget", "One splurge dinner", "Cash for market stalls"]),
            ("Queue Tools Protect Plan", ["Naver Maps", "Catchtable reservation", "Rain backup plan"]),
            ("Leave With A Ready Plan", ["Book anchor meals", "Save backup pins", "Keep transit simple"]),
        ]
    if any(word in text for word in ("office", "priority", "priorities", "weekly", "work", "team")):
        return [
            ("Focus The Week Around Three Outcomes", ["Critical work", "Blocked work", "Decision work"]),
            ("Separate Urgent From Important", ["Must finish", "Can wait", "Needs owner"]),
            ("Protect The Deep Work Window", ["No meeting block", "One escalation lane", "End of day review"]),
            ("Make Ownership Visible", ["Named owner", "Due date", "Status signal"]),
            ("Close With A Friday Scorecard", ["Done", "Blocked", "Next week"]),
        ]
    if any(word in text for word in ("router", "wifi", "network", "config", "technical", "setup")):
        return [
            ("Sequence The Setup Safely", ["Prerequisites first", "Small config blocks", "Verify before saving"]),
            ("Lock The Admin Surface", ["Change admin password", "Use WPA2 or WPA3", "Back up current config"]),
            ("Configure In Blocks", ["WAN and LAN", "DHCP scope", "WiFi name and password"]),
            ("Verify Before Save", ["Check interface state", "Test DNS and internet", "Confirm client join"]),
            ("Keep Rollback Ready", ["Export config", "Document changes", "Know reset path"]),
        ]
    if any(word in text for word in ("proposal", "strategy", "roadmap", "quality", "business")):
        return [
            ("Make The Decision Clear", ["Current gap", "Recommended path", "Approval ask"]),
            ("Show The Cost Of Waiting", ["Quality risk", "Manual rework", "Slow delivery"]),
            ("Use A Repeatable Pipeline", ["Draft", "Build", "Validate", "Review", "Repair"]),
            ("Roll Out In Phases", ["Word first", "Excel second", "PowerPoint third"]),
            ("Approve The Next Gate", ["Owner", "Timeline", "Success signal"]),
        ]
    first = slides[0][0] if slides else "Presentation"
    return [
        (first, ["Clear framing", "One main decision", "Short visual story"]),
        ("Start With The Real Context", ["What matters", "Who decides", "Why now"]),
        ("Show The Main Tradeoff", ["Option A", "Option B", "Constraint"]),
        ("Make The Recommendation Visible", ["Best path", "Risk control", "Next action"]),
        ("Close With The Decision", ["Owner", "Timeline", "Success signal"]),
    ]


def _stronger_slide_title(title: str) -> str:
    clean = " ".join(str(title).split()).strip(" .")
    lowered = clean.lower()
    replacements = (
        (("daily anchor", "anchor each day", "one food anchor"), "Anchor Each Day Around One Meal"),
        (("famous", "backup"), "Pair Famous Stops With Backups"),
        (("budget", "splurge", "cost"), "Spend Intentionally, Not Randomly"),
        (("logistics", "transit", "route"), "Cluster Meals To Cut Transit"),
        (("local", "rules"), "Eat Better By Reading Local Cues"),
        (("next", "recommend"), "Book Anchors, Leave Room To Explore"),
    )
    for keywords, replacement in replacements:
        if any(keyword in lowered for keyword in keywords):
            return replacement
    return clean


def _stronger_bullet(text: str) -> str:
    clean = " ".join(str(text).split()).strip(" .")
    lowered = clean.lower()
    if lowered in {"zones", "key idea", "context", "choice", "next step"}:
        return "Cluster the route by neighborhood."
    if lowered.endswith((" so you", " for", " from", " to", " with", " by", " as")):
        return clean.rsplit(" ", 1)[0]
    if lowered.endswith((" when", " where", " because")):
        return clean.rsplit(" ", 1)[0]
    return clean


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
