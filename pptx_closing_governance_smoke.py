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
    gate.render_pptx_slides = lambda p, d, limit=80: render_pptx_slides(p, d, limit=limit, deadline_seconds=1e-9)
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


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-pptx-governance-") as tmp:
        root = Path(tmp)
        _species_closing_checks(root)
        _rescue_path_checks(root)
        _review_routing_checks()
        _render_timeout_checks(root)
    print("pptx_closing_governance_smoke: ok")


if __name__ == "__main__":
    main()
