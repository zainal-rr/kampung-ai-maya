"""Shared deck species detection.

Single source of truth for what kind of deck a title implies. The narrative
arcs (office_drafter_powerpoint) and the visual identity (office_pptx_palette)
both key off this, so a teaching deck gets a teaching arc AND teaching colors
without two keyword tables drifting apart.

Order matters and mirrors the original routing in _scenario_powerpoint_slides.
"""

from __future__ import annotations

_SPECIES_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("browser", (
        "browser", "google search", "google images", "youtube", "reddit",
        "google flights", "booking.com", "airbnb",
    )),
    ("food", ("food", "restaurant", "cafe")),
    ("travel", ("trip", "travel", "itinerary", "flight", "hotel", "airbnb", "hiking")),
    ("technical", (
        "router", "wifi", "wi-fi", "network", "setup", "technical", "config",
        "configuration", "security", "architecture",
    )),
    ("teaching", (
        "teach", "lesson", "students", "training", "workshop", "school",
        "bootcamp", "classroom",
    )),
    ("review", (
        "retrospective", "postmortem", "post mortem", "sprint review",
        "quarterly review", "monthly review", "project review", "performance review",
    )),
    ("pitch", ("pitch", "investor", "startup", "funding", "fundraising")),
    ("issue", (
        "concern", "awareness", "crisis", "challenges in", "impact of",
        "policy", "issue in", "problem in", "pressure on",
    )),
    ("proposal", ("proposal", "business case", "roadmap", "strategy", "quality", "plan")),
)


def detect_deck_species(title: str) -> str:
    lowered = str(title).lower()
    for species, markers in _SPECIES_MARKERS:
        if any(marker in lowered for marker in markers):
            return species
    return "general"
