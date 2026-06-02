from __future__ import annotations

import tempfile
from pathlib import Path

from pptx import Presentation

from office_drafter import slides_from_markdown
from office_modern_files import choose_pptx_theme, create_pptx


def main() -> None:
    markdown = (
        "# Seoul Food Trip\n\n"
        "## Trip Overview\n\n"
        "1) Two days focused on classic Seoul meals, markets, cafes, and one Korean BBQ dinner.\n"
        "2) Keep each day clustered by area so transit stays manageable and meals do not feel rushed.\n\n"
        "## Day 1 Plan\n\n"
        "1) Start with Myeongdong Kyoja, move to Gwangjang Market, and keep dinner flexible near Myeongdong.\n"
        "2) Use the first day for iconic foods with short walks between stops.\n\n"
        "## Day 2 Plan\n\n"
        "1) Keep breakfast simple, visit a cafe district, and reserve Korean BBQ for the evening.\n"
        "2) Leave buffer time between lunch and dinner so the plan stays realistic.\n\n"
        "## Food And Restaurant Highlights\n\n"
        "1) Prioritize kalguksu, bindaetteok, hotteok, Korean BBQ, and a modern Seoul cafe.\n"
        "2) Save backup restaurants in the same neighborhoods in case queues are long.\n\n"
        "## Budget Notes\n\n"
        "1) Track meals, snacks, cafe stops, transit, and one higher-cost BBQ dinner separately.\n"
        "2) Keep cash for markets and use card for restaurants where accepted.\n\n"
        "## Booking And Transit Notes\n\n"
        "1) Cluster meals by subway area and reserve popular dinners when possible.\n\n"
        "## Recommendations\n\n"
        "1) Use nearby backup restaurants instead of turning one missed meal into a cross-city detour.\n"
    )
    slides = slides_from_markdown(markdown, "2-day Seoul food trip deck")
    _require(len(slides) >= 5, "PowerPoint planner should create a real deck spine")
    _require(slides[0][0] == "2-Day Seoul Food Trip", "title slide should be concise")
    _require(not any("Draft prepared" in " ".join(bullets) for _, bullets in slides), "deck should not use draft placeholder copy")
    _require(any("Budget around one splurge" in title for title, _ in slides), "deck should include a budget decision slide")
    _require(any("Recommendations" in title for title, _ in slides), "deck should include a recommendation slide")

    with tempfile.TemporaryDirectory(prefix="maya-pptx-golden-") as tmp:
        path = Path(tmp) / "seoul-food-trip.pptx"
        create_pptx(path, "2-day Seoul food trip", slides, choose_pptx_theme("2-day Seoul food trip"))
        deck = Presentation(path)
        texts = "\n".join(_deck_text(deck))
        notes = "\n".join(_speaker_notes(deck))
        _require(len(deck.slides) >= 5, "saved PPTX should contain multiple slides")
        _require("Myeongdong Kyoja" in notes and "Gwangjang Market" in notes, "speaker notes should preserve concrete food stops")
        _require("Korean BBQ" in notes, "speaker notes should preserve food highlight")
        _require("Budget around one splurge" in notes, "speaker notes should preserve budget narrative")
        _require("Recommendations turn the itinerary" in notes, "speaker notes should preserve recommendation narrative")
        _require("Talk track:" in notes, "saved PPTX should include speaker notes")
        _require("Myeongdong Kyoja" not in texts, "visible slides should stay concise and move detailed stops to notes")
        _require("Draft prepared" not in texts, "saved PPTX should not contain placeholder title copy")
        _require("Key concept" not in texts, "saved PPTX should not contain old placeholder copy")
    print("powerpoint_golden_artifact_smoke: ok")


def _deck_text(deck: Presentation) -> list[str]:
    values: list[str] = []
    for slide in deck.slides:
        for shape in slide.shapes:
            text = " ".join(getattr(shape, "text", "").split())
            if text:
                values.append(text)
    return values


def _speaker_notes(deck: Presentation) -> list[str]:
    values: list[str] = []
    for slide in deck.slides:
        try:
            text = slide.notes_slide.notes_text_frame.text
        except Exception:
            text = ""
        if text:
            values.append(text)
    return values


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
