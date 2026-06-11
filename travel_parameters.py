from __future__ import annotations

import re


KNOWN_DESTINATIONS = (
    "seoul",
    "tokyo",
    "kyoto",
    "osaka",
    "bangkok",
    "singapore",
    "jakarta",
    "kuala lumpur",
    "kl",
    "penang",
    "melaka",
    "taipei",
    "hong kong",
    "london",
    "paris",
    "new york",
    "istanbul",
    "dubai",
    "bali",
    "almaty",
    "astana",
    "kazakhstan",
    "tashkent",
    "uzbekistan",
)

COUNTRY_DESTINATION_MEMBERS = {
    "kazakhstan": {"almaty", "astana"},
    "uzbekistan": {"tashkent"},
}


GENERIC_DESTINATION_WORDS = {
    "a",
    "an",
    "solo",
    "trip",
    "travel",
    "food",
    "foodie",
    "restaurant",
    "itinerary",
    "document",
    "doc",
    "word",
    "days",
    "day",
    "two",
    "three",
    "four",
    "one",
    "budget",
    "tracker",
    "deck",
    "presentation",
}


def extract_destination(text: str) -> str:
    raw = str(text or "")
    lowered = normalize(raw)
    for destination in KNOWN_DESTINATIONS:
        if _known_destination_match(lowered, destination):
            return "Kuala Lumpur" if destination == "kl" else destination.title()
    proper = _proper_destination(raw)
    return proper if proper and not _generic_destination(proper) else ""


def destination_names_in_text(text: str) -> list[str]:
    lowered = normalize(text)
    found: list[str] = []
    for destination in KNOWN_DESTINATIONS:
        if _known_destination_match(lowered, destination):
            found.append("Kuala Lumpur" if destination == "kl" else destination.title())
    return found


def destination_norm(name: str) -> str:
    raw = normalize(name)
    return "kuala lumpur" if raw == "kl" else raw


def destination_allowed_norms(expected: str) -> set[str]:
    """Names that are valid supporting context for an expected destination."""
    expected_norm = destination_norm(expected)
    allowed = {expected_norm}
    if expected_norm in COUNTRY_DESTINATION_MEMBERS:
        allowed.update(COUNTRY_DESTINATION_MEMBERS[expected_norm])
    for country, cities in COUNTRY_DESTINATION_MEMBERS.items():
        if expected_norm in cities:
            allowed.add(country)
            break
    return allowed


def destination_present_for_expected(expected: str, found: list[str]) -> bool:
    expected_norm = destination_norm(expected)
    found_norms = {destination_norm(item) for item in found}
    if expected_norm in found_norms:
        return True
    if expected_norm in COUNTRY_DESTINATION_MEMBERS:
        return bool(found_norms & COUNTRY_DESTINATION_MEMBERS[expected_norm])
    return False


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).lower()).strip()


def _known_destination_match(text: str, destination: str) -> bool:
    if destination == "kl":
        return bool(re.search(r"\bkl\b", text))
    return bool(re.search(rf"\b{re.escape(destination)}\b", text))


def _proper_destination(text: str) -> str:
    patterns = (
        r"\b(?:in|to)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})\b",
        r"\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})\s+(?:food\s+)?(?:trip|itinerary|travel)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return ""


def _generic_destination(destination: str) -> bool:
    words = {word.lower() for word in re.findall(r"[A-Za-z]+", destination)}
    return not words or bool(words & GENERIC_DESTINATION_WORDS)
