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


def deck_species_prompt_context(species: str) -> str:
    """Species drafting contracts injected into the Gemini deck draft.

    Live finding 2026-06-11: a 'sprint review deck' request with no actual
    sprint data produced fabricated specifics ('Sprint 24', invented
    metrics) — structurally right, semantically wrong. Data-dependent deck
    species must use marked fill-in slots instead of inventing facts."""
    if species == "review":
        return (
            "DECK HONESTY CONTRACT: this is a review/retrospective deck and the user "
            "provided no actual sprint or period data. Do NOT invent sprint numbers, "
            "velocity figures, ticket names, or team member names. Use neutral visible "
            "labels like 'Current Sprint', 'Work Completed', and 'Open Blockers' rather "
            "than fake specifics. If fill-in slots like 'Sprint <N>' or '<X> story points' "
            "are useful, put them in speaker notes or instructions, not visible slide titles."
        )
    if species == "pitch":
        return (
            "DECK HONESTY CONTRACT: do NOT fabricate traction numbers, revenue, customer "
            "names, or market sizes. Use clearly marked fill-in slots ('<N> pilots', "
            "'<RM X> pipeline') for anything the user did not provide, and keep "
            "verifiable claims qualitative. Build a real pitch spine anyway: problem, "
            "customer/use case, solution workflow, operating model, risk/compliance, "
            "and a specific next step or ask."
        )
    if species == "issue":
        return (
            "DECK SEMANTIC CONTRACT: this is an issue/awareness/policy deck, not a sales "
            "pitch. It should explain the concern through local evidence, farm-level or "
            "community-level affected groups, drivers, practical responses, and a next "
            "direction. Use concrete local nouns when the topic provides them; do not hide "
            "behind generic concern wording."
        )
    return ""


def deck_species_review_contract(species: str) -> str:
    if species == "pitch":
        return (
            "Species contract: investor/concept pitch. Judge whether the deck names a real "
            "problem, identifies a customer or use case, explains the solution workflow, "
            "shows an operating or business model, surfaces risks, and ends with a next ask. "
            "If the user gave no metrics, do not require invented traction, revenue, TAM, "
            "or customer names. Mark draft-level only for unresolved visible placeholders, "
            "fabricated exact numbers, missing problem/solution/ask, or generic startup boilerplate."
        )
    if species == "issue":
        return (
            "Species contract: issue/awareness/policy deck. Judge whether the deck explains "
            "the concern, who is affected, the drivers, what responses could work, and the "
            "next direction. Do not expect a sales pitch, financial model, or investor ask. "
            "Mark draft-level only when it is off-topic, generic enough to fit any issue, "
            "missing the affected group/drivers/response arc, or visibly unfinished."
        )
    if species == "teaching":
        return (
            "Species contract: teaching/workshop deck. It should move from learning outcomes "
            "to setup, activity flow, roles/practice, and proof of learning."
        )
    if species == "review":
        return (
            "Species contract: review deck. It should separate delivered work, evidence or "
            "metrics, lessons, decisions, and owners. With no supplied sprint data, visible "
            "copy must stay neutral rather than inventing exact sprint numbers."
        )
    return ""
