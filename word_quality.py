from __future__ import annotations

import re
from dataclasses import dataclass

from word_quality_proposal import proposal_consistency_issues, proposal_prompt_notes
from word_quality_technical import technical_consistency_issues, technical_prompt_notes
from word_quality_travel import travel_consistency_issues, travel_day_headings, travel_default_note
from word_quality_helpers import (
    _generic_filler_issues,
    _has_any,
    _normalize,
    _normalize_heading,
    _required_match,
    _section_depth_issues,
    _title_case_heading,
    _unique_lines,
)


COMMON_BANNED_HEADINGS = (
    "Role And Assumptions",
    "Working Context",
    "Key Decisions",
    "Review Checklist",
    "Needs Verification",
    "Confidence",
)


@dataclass(frozen=True)
class WordQualitySpec:
    intent: str
    label: str
    required_headings: tuple[str, ...]
    prompt_notes: tuple[str, ...]
    min_words: int = 120
    banned_headings: tuple[str, ...] = COMMON_BANNED_HEADINGS
    min_section_words: int = 14


def detect_word_intent(topic: str) -> str:
    lowered = _normalize(topic)
    if _has_any(lowered, ("meeting notes", "meeting minutes", "minutes of meeting", "mom ")):
        return "meeting_notes"
    if _has_any(lowered, ("letter", "email", "refund request", "complaint", "resignation", "cover letter")):
        return "letter"
    if _has_any(lowered, ("standard operating procedure", "operating procedure", "work instruction")) or re.search(r"\bsop\b", lowered):
        return "sop"
    if _has_any(lowered, ("investor", "fundraising", "fund raise", "fund-raise", "seed round", "series a")):
        return "investor_brief"
    if _has_any(lowered, ("proposal", "pitch", "business case", "statement of work", "sow")):
        return "proposal"
    if _has_any(lowered, ("research", "brief", "market scan", "literature", "compare", "comparison", "analysis")):
        return "research_brief"
    if _has_any(lowered, ("checklist", "check list", "preflight", "pre travel", "pre-travel")):
        return "checklist"
    if _has_any(lowered, ("workshop", "training day", "training session", "bootcamp", "hands-on session", "class plan", "lesson plan")):
        return "workshop_plan"
    if _has_any(lowered, ("setup", "configure", "configuration", "install", "technical guide", "troubleshoot", "router", "network", "server", "api", "integration", "runbook")):
        return "technical_guide"
    if _has_any(lowered, ("travel", "trip", "itinerary", "holiday", "vacation", "flight", "hotel", "food trip")):
        return "travel_itinerary"
    if _has_any(lowered, ("report", "audit", "assessment", "postmortem", "post mortem", "review")):
        return "report"
    if _has_any(lowered, ("strategy", "positioning", "go to market", "go-to-market", "content plan")):
        return "strategy"
    if _has_any(lowered, ("plan", "roadmap", "sprint", "workflow")):
        return "plan"
    if _has_any(lowered, ("explain", "explainer", "overview", "what is")):
        return "explainer"
    return "generic"


def word_quality_spec(topic: str) -> WordQualitySpec:
    intent = detect_word_intent(topic)
    if intent == "travel_itinerary":
        daily = travel_day_headings(topic)
        highlight = "Food And Restaurant Highlights" if _has_any(_normalize(topic), ("food", "restaurant", "eat")) else "Place Highlights"
        return WordQualitySpec(
            intent,
            "travel itinerary",
            ("Trip Overview", *daily, highlight, "Budget Notes", "Booking And Transit Notes", "Recommendations"),
            (
                "Make the itinerary concrete enough to use without another prompt.",
                "Include day-level sequencing, realistic timing, local movement notes, and practical recommendations.",
                "For food trips, include actual food/restaurant ideas and budget notes.",
                travel_default_note(topic),
            ),
            170,
        )
    if intent == "technical_guide":
        return WordQualitySpec(
            intent,
            "technical guide",
            ("Purpose", "Prerequisites", "Configuration Steps", "Verification", "Troubleshooting", "Safety Notes", "Next Steps"),
            (
                "Write as an operator-facing guide with prerequisites, numbered steps, verification, and troubleshooting.",
                "Do not invent exact commands, credentials, IPs, limits, or vendor facts unless the topic provides them.",
                "Include rollback or safety notes where changes could break access.",
                *technical_prompt_notes(topic),
            ),
            160,
        )
    if intent == "proposal":
        return WordQualitySpec(
            intent,
            "proposal",
            ("Executive Summary", "Objective", "Scope", "Recommended Approach", "Deliverables", "Timeline", "Risks", "Next Steps"),
            (
                "Write for a decision-maker who needs scope, deliverables, timeline, risks, and the requested decision.",
                "Use concrete deliverables and avoid generic business filler.",
                *proposal_prompt_notes(topic),
            ),
            170,
        )
    if intent == "research_brief":
        return WordQualitySpec(
            intent,
            "research brief",
            ("Research Question", "Scope", "Key Findings", "Evidence", "Risks Or Unknowns", "Sources", "Next Steps"),
            (
                "Separate findings from evidence and unknowns.",
                "Use sources when the topic is current, factual, or product/model related.",
                "Do not overstate certainty when evidence is incomplete.",
            ),
            170,
        )
    if intent == "checklist":
        return WordQualitySpec(
            intent,
            "checklist",
            ("Checklist Overview", "Must Do", "Should Do", "Optional", "Risks Or Watchouts", "Done Criteria"),
            (
                "Write actionable checklist items that can be ticked off mentally.",
                "Group must-do, should-do, optional, risks, and done criteria separately.",
            ),
            120,
        )
    if intent == "meeting_notes":
        return WordQualitySpec(
            intent,
            "meeting notes",
            ("Meeting Summary", "Decisions", "Action Items", "Open Questions", "Follow Up"),
            (
                "Write concise notes with clear decisions, owners when provided, action items, and follow-up.",
                "Do not fabricate attendee names or commitments.",
            ),
            90,
        )
    if intent == "letter":
        return WordQualitySpec(
            intent,
            "letter",
            ("Recipient", "Subject", "Opening", "Request", "Supporting Details", "Requested Resolution", "Closing"),
            (
                "Write a ready-to-send letter in plain professional language.",
                "If recipient details are missing, use neutral wording instead of noisy placeholders.",
            ),
            120,
        )
    if intent == "report":
        return WordQualitySpec(
            intent,
            "report",
            ("Executive Summary", "Findings", "Evidence", "Impact", "Recommendations", "Next Steps"),
            (
                "Write as a practical report with findings, evidence, impact, and recommendations.",
                "Avoid thin summaries that do not support a decision.",
            ),
            150,
        )
    if intent == "sop":
        return WordQualitySpec(
            intent,
            "standard operating procedure",
            ("Purpose And Scope", "Roles And Responsibilities", "Prerequisites", "Step-By-Step Procedure", "Quality Checks", "Exceptions And Escalation", "Revision Notes"),
            (
                "Write numbered, repeatable steps an operator can follow without asking questions.",
                "Name the role responsible for each phase when the topic implies one.",
                "State what to check before declaring the procedure complete, and where to escalate when it fails.",
            ),
            150,
        )
    if intent == "workshop_plan":
        return WordQualitySpec(
            intent,
            "workshop plan",
            ("Workshop Overview", "Learning Objectives", "Materials And Setup", "Session Schedule", "Team Roles", "Assessment And Judging", "Wrap Up And Follow Up"),
            (
                "Write a runnable session plan with timed blocks, not a report about workshops.",
                "Learning objectives must be observable participant outcomes.",
                "Include realistic materials, room setup, and a contingency for late or struggling teams.",
            ),
            150,
        )
    if intent == "investor_brief":
        return WordQualitySpec(
            intent,
            "investor brief",
            ("The Opportunity", "Problem And Timing", "Solution And Product", "Market And Competition", "Business Model", "Traction And Proof", "The Ask", "Key Risks"),
            (
                "Write for an investor deciding whether to take a meeting.",
                "Lead with the opportunity and end with a concrete ask; keep claims checkable.",
                "Separate proven traction from projections so credibility survives diligence.",
            ),
            170,
        )
    if intent == "strategy":
        return WordQualitySpec(
            intent,
            "strategy document",
            ("Strategic Goal", "Audience Or Market", "Strategic Pillars", "Positioning And Differentiation", "Execution Cadence", "Metrics And Review", "Risks", "Next Steps"),
            (
                "Anchor every pillar to the audience or market it serves.",
                "Execution cadence must say what happens weekly or monthly, not vague ambitions.",
                "Metrics must be measurable and tied to the strategic goal.",
            ),
            160,
        )
    if intent == "plan":
        return WordQualitySpec(
            intent,
            "plan",
            ("Goal", "Context", "Workstreams", "Timeline", "Risks", "Next Steps"),
            (
                "Write a plan that can be acted on immediately.",
                "Include workstreams, timeline, risks, and next actions.",
            ),
            140,
        )
    if intent == "explainer":
        return WordQualitySpec(
            intent,
            "explainer",
            ("Plain-English Summary", "Core Concept", "Why It Matters", "Examples", "Common Confusions", "Next Steps"),
            (
                "Explain the topic clearly without turning it into a corporate report.",
                "Use examples and call out common misunderstandings.",
            ),
            120,
        )
    return WordQualitySpec(
        intent,
        "general document",
        ("Overview", "Key Points", "Recommended Approach", "Risks", "Next Steps"),
        (
            "Choose headings that fit the user's real scenario.",
            "Avoid generic role/context boilerplate unless the user explicitly asks for it.",
        ),
        110,
    )


def word_prompt_context(topic: str) -> str:
    spec = word_quality_spec(topic)
    required = "; ".join(spec.required_headings)
    banned = "; ".join(spec.banned_headings)
    notes = "\n".join(f"- {note}" for note in spec.prompt_notes)
    return (
        f"Document intent: {spec.label}.\n"
        f"Use these H2 sections unless the user's wording clearly demands a better equivalent: {required}.\n"
        f"Do not use these boilerplate headings unless explicitly requested: {banned}.\n"
        "Every required section must contain concrete details that fit the user's topic, not meta commentary about what the section should contain.\n"
        "If a required section would be empty, make a reasonable useful assumption or write a concrete default instead of leaving a placeholder.\n"
        f"{notes}"
    )


def canonicalize_word_sections(topic: str, sections: list[tuple[str, list[str]]]) -> list[tuple[str, list[str]]]:
    spec = word_quality_spec(topic)
    buckets: dict[str, list[str]] = {heading: [] for heading in spec.required_headings}
    extras: list[tuple[str, list[str]]] = []
    for heading, lines in sections:
        clean_lines = [line for line in lines if str(line).strip()]
        if not clean_lines:
            continue
        target = _required_match(heading, spec.required_headings)
        if not target and _normalize_heading(heading) in {_normalize_heading(item) for item in spec.banned_headings}:
            target = spec.required_headings[0]
        if target:
            buckets[target].extend(clean_lines)
        else:
            extras.append((_title_case_heading(heading), clean_lines[:6]))
    ordered = [(heading, _unique_lines(buckets[heading])[:6]) for heading in spec.required_headings if buckets[heading]]
    seen = {_normalize_heading(heading) for heading, _ in ordered}
    for heading, lines in extras:
        if _normalize_heading(heading) not in seen:
            ordered.append((heading, lines))
            seen.add(_normalize_heading(heading))
    limit = max(8, len(spec.required_headings) + 2)
    return ordered[:limit] or sections


def validate_word_doc_quality(
    topic: str,
    paragraphs: list[str],
    headings: list[str],
    sections: list[tuple[str, list[str]]] | None = None,
) -> list[str]:
    if not topic.strip():
        return []
    spec = word_quality_spec(topic)
    issues: list[str] = []
    normalized_headings = {_normalize_heading(heading) for heading in headings}
    banned = {_normalize_heading(heading) for heading in spec.banned_headings}
    for heading in sorted(normalized_headings & banned):
        issues.append(f"boilerplate heading should not be used: {heading}")
    missing = [required for required in spec.required_headings if not _required_match(required, headings)]
    if missing:
        issues.append("missing scenario headings: " + ", ".join(missing[:4]))
    word_count = sum(len(item.split()) for item in paragraphs)
    if word_count < spec.min_words:
        issues.append(f"{spec.label} is too thin for first-draft delivery")
    issues.extend(_generic_filler_issues(paragraphs))
    if sections is not None:
        issues.extend(_section_depth_issues(spec, sections))
    if spec.intent == "travel_itinerary":
        issues.extend(travel_consistency_issues(topic, paragraphs, headings))
    if spec.intent == "technical_guide":
        issues.extend(technical_consistency_issues(topic, paragraphs))
    if spec.intent == "proposal":
        issues.extend(proposal_consistency_issues(paragraphs))
    return issues




















