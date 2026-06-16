from __future__ import annotations

import re

from artifact_qa_governance import MECHANICAL, OPEN_WORLD, QAIssue, blocker, warning
from travel_parameters import (
    destination_allowed_norms,
    destination_names_in_text,
    destination_present_for_expected,
    extract_destination,
)


def travel_day_headings(topic: str) -> tuple[str, ...]:
    days = explicit_day_count(topic) or default_travel_days(topic)
    # A stated duration must produce one heading per day so a 9-day itinerary
    # cannot hide behind a single "Daily Plan" section. 12 matches the largest
    # word-number explicit_day_count can parse.
    if 1 < days <= 12:
        return tuple(f"Day {index} Plan" for index in range(1, days + 1))
    return ("Daily Plan",)


def explicit_day_count(topic: str) -> int:
    lowered = normalize(topic)
    match = re.search(r"\b(\d+)\s*[- ]?\s*(?:day|days)\b", lowered)
    if match:
        return int(match.group(1))
    words = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
    }
    for word, count in words.items():
        if re.search(rf"\b{word}\s*[- ]?\s*(?:day|days)\b", lowered):
            return count
    return 0


def default_travel_days(topic: str) -> int:
    lowered = normalize(topic)
    if has_any(lowered, ("food trip", "restaurant", "eat", "eating", "foodie", "food highlights")):
        return 2
    if has_any(lowered, ("city", "weekend", "short trip")):
        return 2
    return 3


def travel_default_note(topic: str) -> str:
    if explicit_day_count(topic):
        return "Use the user's stated duration exactly."
    days = default_travel_days(topic)
    return f"The user did not state a duration, so use a compact {days}-day default and say it is an assumption."


def travel_consistency_issues(topic: str, paragraphs: list[str], headings: list[str]) -> list[str]:
    return [issue.message for issue in travel_consistency_issue_details(topic, paragraphs, headings) if issue.blocks_delivery]


def travel_consistency_issue_details(topic: str, paragraphs: list[str], headings: list[str]) -> list[QAIssue]:
    expected = explicit_day_count(topic) or default_travel_days(topic)
    issues: list[QAIssue] = []
    issues.extend(destination_consistency_issue_details(topic, paragraphs, headings))
    if expected <= 1 or expected > 12:
        return issues
    heading_norms = [normalize_heading(heading) for heading in headings]
    missing = [f"Day {day} Plan" for day in range(1, expected + 1) if f"day {day} plan" not in heading_norms]
    if missing:
        issues.append(blocker(
            "travel.day_headings_missing",
            MECHANICAL,
            "missing day-level travel headings: " + ", ".join(missing),
        ))
    joined = " ".join(paragraphs).lower()
    declared = {int(item) for item in re.findall(r"\b(\d+)\s*[- ]?\s*day\b", joined)}
    wrong = sorted(day for day in declared if day != expected)
    if wrong:
        issues.append(blocker(
            "travel.day_count_mismatch",
            MECHANICAL,
            f"travel document declares {wrong[0]} days but expected {expected}",
        ))
    return issues


def destination_consistency_issues(topic: str, paragraphs: list[str], headings: list[str]) -> list[str]:
    return [issue.message for issue in destination_consistency_issue_details(topic, paragraphs, headings) if issue.blocks_delivery]


def destination_consistency_issue_details(topic: str, paragraphs: list[str], headings: list[str]) -> list[QAIssue]:
    expected = extract_destination(topic)
    if not expected:
        return []
    joined = " ".join([*headings, *paragraphs])
    found = destination_names_in_text(joined)
    allowed_norms = destination_allowed_norms(expected)
    issues: list[QAIssue] = []
    expected_present = destination_present_for_expected(expected, found)
    heading_found = destination_names_in_text(" ".join(headings))
    heading_wrong = sorted(item for item in heading_found if normalize(item) not in allowed_norms)
    wrong = sorted(item for item in found if normalize(item) not in allowed_norms)
    strong_drift = (not expected_present) and bool(heading_wrong)
    if not expected_present:
        issue_factory = blocker if strong_drift else warning
        issues.append(issue_factory(
            "travel.destination_missing",
            OPEN_WORLD,
            f"travel document missing expected destination: {expected}",
            evidence=f"found={', '.join(found) or 'none'}",
        ))
    if wrong:
        issue_factory = blocker if strong_drift else warning
        issues.append(issue_factory(
            "travel.destination_match",
            OPEN_WORLD,
            f"travel document destination mismatch: expected {expected}, found {wrong[0]}",
            evidence=f"all_found={', '.join(found)}; headings_found={', '.join(heading_found)}",
        ))
    return issues


def has_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).lower()).strip()


def normalize_heading(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()
