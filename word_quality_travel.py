from __future__ import annotations

import re


def travel_day_headings(topic: str) -> tuple[str, ...]:
    days = explicit_day_count(topic) or default_travel_days(topic)
    if 1 < days <= 4:
        return tuple(f"Day {index} Plan" for index in range(1, days + 1))
    return ("Daily Plan",)


def explicit_day_count(topic: str) -> int:
    lowered = normalize(topic)
    match = re.search(r"\b(\d+)\s*[- ]?\s*(?:day|days)\b", lowered)
    if match:
        return int(match.group(1))
    words = {"one": 1, "two": 2, "three": 3, "four": 4}
    for word, count in words.items():
        if re.search(rf"\b{word}\s+(?:day|days)\b", lowered):
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
    expected = explicit_day_count(topic) or default_travel_days(topic)
    if expected <= 1 or expected > 4:
        return []
    issues: list[str] = []
    heading_norms = [normalize_heading(heading) for heading in headings]
    missing = [f"Day {day} Plan" for day in range(1, expected + 1) if f"day {day} plan" not in heading_norms]
    if missing:
        issues.append("missing day-level travel headings: " + ", ".join(missing))
    joined = " ".join(paragraphs).lower()
    declared = {int(item) for item in re.findall(r"\b(\d+)\s*[- ]?\s*day\b", joined)}
    wrong = sorted(day for day in declared if day != expected)
    if wrong:
        issues.append(f"travel document declares {wrong[0]} days but expected {expected}")
    return issues


def has_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).lower()).strip()


def normalize_heading(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()
