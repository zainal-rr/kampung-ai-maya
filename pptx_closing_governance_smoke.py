"""Flow-level PPTX governance smoke (Phase 4 live failures, 2026-06-11).

The earlier drafter-level smoke passed while live decks leaked the banned
closing, because the leak lived DOWNSTREAM of the drafter (title rewriter +
rescue templates). This smoke asserts on the SAVED .pptx files, after every
transformation layer, plus the routing and render-timeout fixes:

1. Four species decks end with four DIFFERENT closings, and no slide in any
   deck is titled "Make The Recommendation Clear".
2. The rescue-template path (the actual live leak source) also renders a
   specific closing, not the banned generic and not a bare "Recommendation".
3. "make a sprint review deck" is CREATION, not review-of-last-deck;
   explicit review requests still route to review.
4. A render timeout is a warning (deck passes, note recorded), while real
   render output still matches slide count on the normal path.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from pptx import Presentation as ReadPresentation

from office_drafter import slides_from_markdown
from office_modern_files import create_pptx
from pptx_quality_gate import inspect_pptx_quality
from pptx_slide_repair import rescue_slides
from presentation_design_review import wants_presentation_review

BANNED_CLOSING = "make the recommendation clear"

MD = (
    "## Overview\nThe topic needs a clear structure.\n"
    "## Details\nKey facts and steps live here.\n"
    "## Recommendations\nDo the practical thing first.\n"
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _saved_titles(path: Path) -> list[str]:
    deck = ReadPresentation(path)
    titles = []
    for slide in deck.slides:
        title = ""
        for shape in slide.shapes:
            text = getattr(shape, "text", "").strip()
            if text:
                title = text.split("\n")[0]
                break
        titles.append(title)
    return titles


def _species_closing_checks(root: Path) -> None:
    cases = {
        "teaching": "make a presentation about a school robotics workshop",
        "review": "make a sprint review deck for the team",
        "pitch": "make an investor pitch deck for a drone inspection startup",
        "issue": "make a presentation about agriculture concern in Malaysia",
    }
    closings: dict[str, str] = {}
    for label, title in cases.items():
        path = create_pptx(root / f"{label}.pptx", title, slides_from_markdown(MD, title))
        titles = _saved_titles(path)
        joined = " | ".join(titles).lower()
        _require(BANNED_CLOSING not in joined, f"{label}: banned closing leaked into saved deck: {titles}")
        closings[label] = titles[-1].lower()
    _require(len(set(closings.values())) == 4, f"species closings must differ in SAVED decks: {closings}")
    print("  four species decks, four closings, no banned title: ok")


def _rescue_path_checks(root: Path) -> None:
    # The live leak source: rescue templates + title rewriter.
    slides = rescue_slides([], "school robotics workshop kits judging learning goals")
    _require(len(slides) >= 4, "rescue template should produce a full deck")
    path = create_pptx(root / "rescue.pptx", "school robotics workshop deck", slides)
    titles = _saved_titles(path)
    closing = titles[-1].lower()
    _require(BANNED_CLOSING not in " ".join(titles).lower(), f"rescue path leaked banned closing: {titles}")
    _require(closing.strip() != "recommendation", f"rescue closing collapsed to bare 'Recommendation': {titles}")
    _require(len(closing) >= 8, f"rescue closing too weak: {closing!r}")
    print("  rescue-template path keeps a real closing: ok")


def _review_routing_checks() -> None:
    creation = (
        "make a sprint review deck for the team",
        "create a performance review deck",
        "make a quarterly review presentation for the board",
        "draft a deck about our code review process",
    )
    for text in creation:
        _require(not wants_presentation_review(text), f"creation request misrouted to review: {text!r}")
    review = (
        "review the Meta Ray-Ban Display presentation design",  # pinned by existing smoke
        "review this deck",
        "critique my last presentation",
        "check the latest slides",
    )
    for text in review:
        _require(wants_presentation_review(text), f"review request lost: {text!r}")
    print("  sprint-review routing (creation vs review): ok")


def _render_timeout_checks(root: Path) -> None:
    # A deliberately clean deck so only the render path is under test.
    clean_slides = [
        ("Workshop Outcomes Set The Day", ["Participants build one robot.", "Teams demo at the end."]),
        ("Practice Time Drives Learning", ["Hands-on blocks come first.", "Helpers rove between teams."]),
    ]
    path = create_pptx(root / "timeout.pptx", "robotics workshop outcomes deck", clean_slides)
    # Force the timeout path deterministically via a microscopic deadline.
    import pptx_quality_gate as gate
    from pptx_slide_renderer import render_pptx_slides

    original = gate.render_pptx_slides
    gate.render_pptx_slides = lambda p, d, limit=80, deadline_seconds=None: render_pptx_slides(
        p, d, limit=limit, deadline_seconds=1e-9
    )
    try:
        result = gate.inspect_pptx_quality(path)
    finally:
        gate.render_pptx_slides = original
    _require(result.passed, f"render timeout must not block a clean deck: {result.issues}")
    _require(result.notes and "render qa skipped" in result.notes[0].lower(), f"timeout note missing: {result.notes}")
    _require("not" not in result.summary().lower().split("visual qa ")[1][:10], "summary should read as passed")
    # Normal path: rendering still works and counts match.
    normal = inspect_pptx_quality(path)
    _require(normal.passed and not normal.notes, f"normal render path regressed: {normal.issues} {normal.notes}")
    _require(len(normal.images) == len(_saved_titles(path)), "rendered image count must match slides")
    print("  render timeout = warning, normal render intact: ok")


def _storage_stall_checks(root: Path) -> None:
    """Live P5 failure shape: OSError [Errno 60] inside image.save() on a
    syncing volume. Must classify as warning, not blocker."""
    import pptx_quality_gate as gate

    clean_slides = [
        ("Workshop Outcomes Set The Day", ["Participants build one robot.", "Teams demo at the end."]),
        ("Practice Time Drives Learning", ["Hands-on blocks come first.", "Helpers rove between teams."]),
    ]
    path = create_pptx(root / "stall.pptx", "robotics workshop outcomes deck", clean_slides)

    def _stalled(*_args, **_kwargs):
        raise OSError(60, "Operation timed out", str(root / "slide-01.jpg"))

    original = gate.render_pptx_slides
    gate.render_pptx_slides = _stalled
    try:
        result = gate.inspect_pptx_quality(path)
    finally:
        gate.render_pptx_slides = original
    _require(result.passed, f"storage-stall (Errno 60) must not block a clean deck: {result.issues}")
    _require(result.notes and "i/o timed out" in result.notes[0].lower(), f"stall note missing: {result.notes}")
    # A real render failure must still block.
    gate.render_pptx_slides = lambda *a, **k: (_ for _ in ()).throw(ValueError("corrupt"))
    try:
        broken = gate.inspect_pptx_quality(path)
    finally:
        gate.render_pptx_slides = original
    _require(not broken.passed and any("render failed" in i for i in broken.issues), "real render failures must stay blockers")
    print("  storage stall (Errno 60) = warning, real failure = blocker: ok")


def _visual_availability_checks(root: Path) -> None:
    """Live P3 failure shape: image generation failed/stalled for a visual
    topic and the deck was blocked for it. Availability is now a note."""
    import asyncio
    import tempfile as _tempfile

    import pptx_document_flow as flow
    from storage import init_db
    from harness_artifact_store import init_harness_artifact_db

    async def _case() -> None:
        with _tempfile.TemporaryDirectory(prefix="maya-visual-avail-") as tmp2:
            db = str(Path(tmp2) / "t.db")
            await init_db(db)
            await init_harness_artifact_db(db)
            title = "make an investor pitch deck for a drone inspection startup"  # visual topic ("pitch")

            async def fake_assets_unavailable(_path, _title, max_images=None):
                return False, "Gemini image generation failed: [Errno 60] Operation timed out"

            async def fake_polish(_db, _path):
                return "Design polish: good. Clear structure.", False

            original_assets = flow.add_gemini_visual_asset
            original_polish = flow.claude_polish_grade
            flow.add_gemini_visual_asset = fake_assets_unavailable
            flow.claude_polish_grade = fake_polish
            try:
                slides = [
                    ("Drone Inspection Has A Clear Use Case", ["Towers and roofs cost less by air.", "Insurers accept drone reports."]),
                    ("Start Narrow", ["Pick two inspection packages.", "Price by risk and output."]),
                ]
                qa, _note = await flow._run_powerpoint_attempt(db, root / "drone.pptx", title, slides, "smoke-run", False, None)
            finally:
                flow.add_gemini_visual_asset = original_assets
                flow.claude_polish_grade = original_polish
            _require(qa.passed, f"image unavailability must not block a clean visual-topic deck: {qa.issues}")
            _require(qa.notes and "visual assets unavailable" in qa.notes[0], f"availability note missing: {qa.notes}")

    asyncio.run(_case())
    print("  visual-asset unavailability = note, not blocker: ok")


def _fragment_cap_checks() -> None:
    """Live polish rejections 2026-06-11 were manufactured by hard word caps.
    The exact live fragments are the fixtures."""
    from office_pptx_text import _short, _title_words

    # Grace rule: complete claims modestly over the cap survive whole.
    full = _title_words("Inspecting Critical Infrastructure Is Still Done Manually", 7)
    _require(full.lower().endswith("manually"), f"grace rule failed, fragment kept: {full!r}")
    flows = _title_words("All Five Core User Flows", 4)
    _require(flows.lower().endswith("flows"), f"label grace failed: {flows!r}")
    # When a character cut is unavoidable, never end on a dangling word.
    cut = _short("Inspecting Critical Infrastructure Is Still Done Manually Every Quarter By Two Teams", 54, complete=False)
    _require(not cut.lower().split()[-1] in {"is", "still", "done", "of", "by", "to", "the"}, f"layout cut ends dangling: {cut!r}")
    manual = _title_words("Eliminate Weeks Of Manual Inspection Backlog Within One Quarter", 5)
    _require(not manual.lower().endswith(" of") and not manual.lower().endswith(" manual"), f"dangling tail kept: {manual!r}")
    from pptx_polish_review import local_polish_issues
    with tempfile.TemporaryDirectory(prefix="maya-label-polish-") as tmp:
        label_path = create_pptx(
            Path(tmp) / "label.pptx",
            "drone inspection deck",
            [("Compliance Must Be Built In", ["Flight permissions", "Safety perimeter", "Data handling"])],
        )
        _require(
            not any("incomplete" in issue for issue in local_polish_issues(label_path)),
            "short title-case label ending in 'In' should not be incomplete",
        )
    print("  fragment-free title caps (live fixtures): ok")


def _visual_budget_checks(root: Path) -> None:
    """Live P3: 313.9s in the visual stage. The stage now has a wall-clock
    budget that lands in the availability-note path."""
    import asyncio

    import pptx_document_flow as flow
    from storage import init_db
    from harness_artifact_store import init_harness_artifact_db

    async def _case() -> None:
        import tempfile as _tempfile

        with _tempfile.TemporaryDirectory(prefix="maya-visual-budget-") as tmp2:
            db = str(Path(tmp2) / "t.db")
            await init_db(db)
            await init_harness_artifact_db(db)
            title = "make an investor pitch deck for a drone inspection startup"

            async def slow_assets(_path, _title, max_images=None):
                await asyncio.sleep(30)
                return True, "never reached"

            async def fake_polish(_db, _path):
                return "Design polish: good.", False

            original_assets = flow.add_gemini_visual_asset
            original_polish = flow.claude_polish_grade
            original_budget = os.environ.get("MAYA_PPTX_VISUAL_BUDGET_SECONDS")
            flow.add_gemini_visual_asset = slow_assets
            flow.claude_polish_grade = fake_polish
            os.environ["MAYA_PPTX_VISUAL_BUDGET_SECONDS"] = "1"
            try:
                slides = [
                    ("Drone Inspection Has A Clear Use Case", ["Towers and roofs cost less by air.", "Insurers accept drone reports."]),
                    ("Start Narrow", ["Pick two inspection packages.", "Price by risk and output."]),
                ]
                qa, _note = await flow._run_powerpoint_attempt(db, root / "budget.pptx", title, slides, "smoke-run", False, None)
            finally:
                flow.add_gemini_visual_asset = original_assets
                flow.claude_polish_grade = original_polish
                if original_budget is None:
                    os.environ.pop("MAYA_PPTX_VISUAL_BUDGET_SECONDS", None)
                else:
                    os.environ["MAYA_PPTX_VISUAL_BUDGET_SECONDS"] = original_budget
            _require(qa.passed, f"visual budget timeout must not block the deck: {qa.issues}")
            _require(qa.notes and "exceeded its 1s budget" in qa.notes[0], f"budget note missing: {qa.notes}")

    asyncio.run(_case())
    print("  visual stage wall-clock budget = note: ok")


def _scratch_and_honesty_checks() -> None:
    from pptx_visual_assets import _image_scratch_dir
    from deck_species import deck_species_prompt_context
    from pptx_slide_repair import rescue_slides

    scratch = str(_image_scratch_dir())
    _require("Desktop" not in scratch, f"image scratch must not default to Desktop: {scratch}")
    review_contract = deck_species_prompt_context("review")
    _require("Do NOT invent sprint numbers" in review_contract and "visible slide titles" in review_contract,
             f"review honesty contract wrong: {review_contract[:80]}")
    _require("fabricate" in deck_species_prompt_context("pitch"), "pitch honesty contract missing")
    _require(deck_species_prompt_context("teaching") == "", "non-data species must have no contract")
    sprint_rescue = rescue_slides([], "make a sprint review deck for the team")
    rescue_titles = " ".join(title for title, _ in sprint_rescue).lower()
    _require("current sprint review" in rescue_titles, f"sprint rescue did not stay sprint-specific: {sprint_rescue}")
    _require("artifact quality" not in rescue_titles, f"sprint rescue fell into artifact-quality template: {sprint_rescue}")
    print("  image scratch dir + deck honesty contracts + sprint rescue: ok")


def _image_policy_checks() -> None:
    from pptx_polish_review import image_policy_line

    non_visual = image_policy_line("make a presentation about a school robotics workshop")
    _require("does not use generated images" in non_visual, f"non-visual policy wrong: {non_visual}")
    visual = image_policy_line("make an investor pitch deck for a drone startup")
    _require("never" in visual and "draft-level" in visual, f"visual policy wrong: {visual}")
    print("  image policy single source of truth: ok")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-pptx-governance-") as tmp:
        root = Path(tmp)
        _species_closing_checks(root)
        _rescue_path_checks(root)
        _review_routing_checks()
        _render_timeout_checks(root)
        _storage_stall_checks(root)
        _visual_availability_checks(root)
        _image_policy_checks()
        _fragment_cap_checks()
        _visual_budget_checks(root)
        _scratch_and_honesty_checks()
    print("pptx_closing_governance_smoke: ok")


if __name__ == "__main__":
    main()
