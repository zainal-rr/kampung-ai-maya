"""Deterministic species regression smoke using real prompt shapes.

Covers the review findings on document sameness:
1. Domain Excel trackers get distinct schemas (no shared office skeleton).
2. "Kampung AI <topic>" is not blocked from species by the money guard.
3. A 9-day itinerary must carry Day 1..Day 9 headings and is validated.
4. Deck arcs (teaching/review/pitch/issue) produce distinct closings.
5. General decks vary their closing by topic.
6. The live batch validator no longer passes Word docs on word count alone.
"""

from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


from pathlib import Path

from document_actions_content_helpers import _budget_topic, _task_tracker_topic
from excel_species import detect_excel_species, species_rows
from office_drafter import slides_from_markdown, spreadsheet_from_markdown
from word_quality import detect_word_intent, word_quality_spec
from word_quality_travel import travel_consistency_issues


MD = (
    "## Overview\nThe topic needs a clear working structure.\n"
    "## Details\nKey facts and steps live here.\n"
    "## Risks\nWatch the main failure mode early.\n"
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _excel_species_checks() -> None:
    cases = {
        "make a youtube tracker for my video channel project": "content_calendar",
        "make an agriculture tracker for the farm": "operations_log",
        "make a coding sprint tracker for the repo": "dev_tracker",
        "make an equipment inventory for the studio": "inventory",
        "Kampung AI YouTube content calendar": "content_calendar",
    }
    schemas = set()
    for topic, want in cases.items():
        got = detect_excel_species(topic)
        _require(got == want, f"{topic!r} -> {got}, wanted {want}")
        headers, _rows = species_rows(want, topic, [("Overview", ["First item"])])
        schemas.add(tuple(headers))
    _require(len(schemas) == 4, "domain species should produce distinct schemas")
    _require(detect_excel_species("monthly budget tracker for home") is None, "budget must stay in money lanes")
    _require(detect_excel_species("Excel tracker for Kampung AI cost") is None, "cost must stay in money lanes")
    _require(not _task_tracker_topic("make a coding sprint tracker for the repo"), "coding tracker must not use office skeleton")
    _require(_task_tracker_topic("office task tracker with owner due date status priority"), "office task tracker lane must survive")
    _require(_budget_topic("monthly budget tracker for home"), "household budget lane must survive")
    headers, rows = species_rows("inventory", "studio equipment", [("Cameras", ["Sony body"])])
    _require(any("=SUM(" in str(cell) for cell in rows[-1]), "inventory should keep a total formula row")
    _require(detect_excel_species("liquidity gap and cash flow analysis workbook") == "financial_model",
             "finance workbook should get the financial model species")
    _require(detect_excel_species("road trip packing checklist sheet") != "financial_model",
             "'roa' must not substring-match 'road'")
    fin_headers, fin_rows = species_rows(
        "financial_model",
        "liquidity gap analysis",
        [("Inflows", ["Loan collections expected"]), ("Obligations", ["Debt service due"])],
    )
    _require("Inflow" in fin_headers and "Cumulative Net" in fin_headers, f"financial model schema wrong: {fin_headers}")
    joined = " ".join(str(cell) for row in fin_rows for cell in row)
    _require("=SUM(" in joined and "Coverage ratio" in joined, "financial model must compute gap and coverage ratio")
    headers, _rows = spreadsheet_from_markdown("Kampung AI YouTube content calendar", MD)
    _require(headers[0] == "Week Or Date", f"kampung ai content calendar got wrong schema: {headers}")


def _word_species_checks() -> None:
    cases = {
        "Workshop plan for a school robotics day with objectives and assessment": "workshop_plan",
        "Write an SOP for onboarding new staff": "sop",
        "Investor brief for my drone inspection startup": "investor_brief",
        "YouTube content strategy for an AI assistant channel": "strategy",
        "nine day Kazakhstan itinerary doc": "travel_itinerary",
    }
    for topic, want in cases.items():
        got = detect_word_intent(topic)
        _require(got == want, f"{topic!r} -> {got}, wanted {want}")


def _travel_day_checks() -> None:
    topic = "nine day Kazakhstan itinerary doc"
    spec = word_quality_spec(topic)
    for day in range(1, 10):
        _require(f"Day {day} Plan" in spec.required_headings, f"Day {day} Plan missing for 9-day itinerary")
    short_headings = ["Trip Overview", "Daily Plan", "Budget Notes"]
    issues = travel_consistency_issues(topic, ["A nine day route across Kazakhstan."], short_headings)
    _require(any("missing day-level" in issue for issue in issues), f"9-day doc without day headings must fail: {issues}")
    full_headings = ["Trip Overview", *[f"Day {day} Plan" for day in range(1, 10)], "Budget Notes"]
    issues = travel_consistency_issues(topic, ["A 9 day route across Kazakhstan."], full_headings)
    _require(not any("missing day-level" in issue for issue in issues), f"full 9-day doc should not be flagged: {issues}")
    issues = travel_consistency_issues(
        topic,
        ["A nine day route across Kazakhstan covering Almaty, Astana, Charyn Canyon, and Turkistan."],
        full_headings,
    )
    _require(
        not any("destination mismatch" in issue or "missing expected destination" in issue for issue in issues),
        f"country itinerary should allow in-country city names: {issues}",
    )
    city_issues = travel_consistency_issues(
        "three day Almaty itinerary",
        ["A three day Almaty route in Kazakhstan with mountain and city stops."],
        ["Trip Overview", "Day 1 Plan", "Day 2 Plan", "Day 3 Plan", "Place Highlights", "Budget Notes", "Booking And Transit Notes", "Recommendations"],
    )
    _require(
        not any("destination mismatch" in issue or "missing expected destination" in issue for issue in city_issues),
        f"city itinerary should allow parent country context: {city_issues}",
    )


def _deck_arc_checks() -> None:
    closings = {}
    for label, title in {
        "teaching": "school robotics workshop deck",
        "review": "sprint review deck for the team",
        "pitch": "investor pitch deck for drone startup",
        "issue": "agriculture concern in Malaysia PowerPoint",
    }.items():
        slides = slides_from_markdown(MD, title)
        closings[label] = slides[-1][0].lower()
        _require(
            "recommendation clear" not in " ".join(t for t, _ in slides).lower(),
            f"{label} deck must not reuse the universal recommendation closing",
        )
    _require(len(set(closings.values())) == 4, f"arc closings should differ: {closings}")
    _require(
        any(marker in closings["issue"] for marker in ("adoptable", "works", "way forward")),
        f"issue arc closing missing: {closings['issue']}",
    )
    general_decide = slides_from_markdown(MD, "help me decide which laptop to buy deck")[-1][0].lower()
    general_explain = slides_from_markdown(MD, "overview of malaysian coffee history deck")[-1][0].lower()
    _require(general_decide != general_explain, "general decks should vary closing by topic")


def _live_batch_validator_checks() -> None:
    source = (Path(__file__).parent / "imac_document_creation_batch_live.py").read_text(encoding="utf-8")
    _require(
        "or len(text.split()) >= 260" not in source,
        "live batch validator must not pass Word docs on word count when QA fails",
    )


def _deck_visual_checks() -> None:
    import tempfile

    from pptx import Presentation as ReadPresentation

    from office_modern_files import create_pptx
    from office_pptx_palette import palette_for

    # Species palettes must actually differ, and stay deterministic.
    teaching = palette_for("school robotics workshop deck", "dark")
    review = palette_for("sprint review deck for the team", "dark")
    issue = palette_for("agriculture concern in Malaysia PowerPoint", "dark")
    technical = palette_for("Kampung AI architecture deck", "dark")
    accents = {str(p.accent) for p in (teaching, review, issue)}
    _require(len(accents) == 3, f"species accents should differ: {accents}")
    _require(str(technical.accent) == "79A7FF", "technical decks must keep the original blue accent")
    _require(str(palette_for("school robotics workshop deck", "dark").accent) == str(teaching.accent), "palette must be deterministic")

    # The saved files must carry the species accent (left accent bar shape)
    # AND a species-tinted background that stays in the dark family.
    slides = [("Title", ["One line"]), ("Point", ["A", "B", "C"])]
    with tempfile.TemporaryDirectory(prefix="maya-deck-visual-") as tmp:
        root = Path(tmp)
        bars = {}
        backgrounds = {}
        for label, title in {
            "teaching": "school robotics workshop deck",
            "review": "sprint review deck for the team",
            "issue": "agriculture concern in Malaysia PowerPoint",
        }.items():
            path = create_pptx(root / f"{label}.pptx", title, slides)
            deck = ReadPresentation(path)
            shape = deck.slides[0].shapes[0]  # accent bar is drawn first
            bars[label] = str(shape.fill.fore_color.rgb)
            rgb = str(deck.slides[0].background.fill.fore_color.rgb)
            backgrounds[label] = rgb
            _require(max(int(rgb[i:i + 2], 16) for i in (0, 2, 4)) < 80, f"{label} dark background must stay dark: {rgb}")
        _require(len(set(bars.values())) == 3, f"saved decks should carry distinct accent bars: {bars}")
        _require(len(set(backgrounds.values())) == 3, f"saved decks should carry distinct backgrounds: {backgrounds}")
        technical_path = create_pptx(root / "technical.pptx", "Kampung AI architecture deck", slides)
        technical_rgb = str(ReadPresentation(technical_path).slides[0].background.fill.fore_color.rgb)
        _require(technical_rgb == "12161C", f"technical deck must keep the base dark background: {technical_rgb}")


def main() -> None:
    _excel_species_checks()
    _word_species_checks()
    _travel_day_checks()
    _deck_arc_checks()
    _deck_visual_checks()
    _live_batch_validator_checks()
    print("document_species_smoke: ok")


if __name__ == "__main__":
    main()
