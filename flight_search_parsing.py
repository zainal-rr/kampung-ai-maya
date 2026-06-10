from __future__ import annotations

import re
from datetime import datetime

from active_context_models import ActiveContext
from flight_search_models import FlightDetails, KNOWN_DESTINATIONS, MONTHS


def extract_flight_details(question: str, context: ActiveContext) -> FlightDetails:
    joined = "\n".join(
        part
        for part in (
            question,
            context.active_title,
            context.selected_content,
            context.nearby_context,
            context.document_context,
        )
        if part
    )
    origin = _origin(joined)
    assumptions = []
    if not re.search(r"\bfrom\s+|Kuala Lumpur|Malaysia|KUL\b", joined, re.I):
        assumptions.append("origin Kuala Lumpur because no origin was explicit")
    destination = _destination(question, joined)
    explicit_destination = bool(destination)
    question_dates = _dates(question)
    use_context_dates = not explicit_destination or _is_context_trip_request(question)
    dates = question_dates if question_dates else (_dates(joined) if use_context_dates else [])
    missing = []
    if not destination:
        missing.append("destination")
    if not dates:
        missing.append("departure date")
    depart = dates[0] if dates else ""
    return_date = dates[1] if len(dates) > 1 else ""
    if return_date:
        assumptions.append("return trip because two dates were provided")
    elif dates:
        assumptions.append("one way because only one date was provided")
    else:
        assumptions.append("one way unless you give me a return date")
    return FlightDetails(origin=origin, destination=destination, depart=depart, return_date=return_date, one_way=not bool(return_date), missing=tuple(missing), assumptions=tuple(assumptions))


def _origin(text: str) -> str:
    explicit = _first_match(text, (r"\bfrom\s+([A-Z][A-Za-z ]{2,45}?)(?:\s+to|\s+on|\s+around|$)",))
    if explicit:
        return _clean_place(explicit)
    if re.search(r"\b(Kuala Lumpur|Malaysia|KUL)\b", text, re.I):
        return "Kuala Lumpur"
    return "Kuala Lumpur"


def _destination(question: str, text: str) -> str:
    explicit = _first_match(question, (r"\bto\s+([A-Za-z][A-Za-z ]{2,45}?)(?:\s+from|\s+on|\s+around|\s+tomorrow|\s+today|$)",))
    if explicit:
        place = _clean_place(explicit)
        return "Osaka" if place.lower() == "kyoto" else place
    explicit = _known_place_from_question(question)
    if explicit:
        return "Osaka" if explicit.lower() == "kyoto" else explicit
    if re.search(r"\b(Osaka|Kansai|KIX)\b", text, re.I):
        return "Osaka"
    if re.search(r"\bKyoto\b", text, re.I):
        return "Osaka"
    return ""


def _known_place_from_question(question: str) -> str:
    for place in KNOWN_DESTINATIONS:
        if re.search(rf"\b{re.escape(place)}\b", question, re.I):
            return place
    return ""


def _is_context_trip_request(question: str) -> bool:
    lowered = question.lower()
    return any(phrase in lowered for phrase in ("this trip", "my trip", "the trip", "this itinerary", "current itinerary"))


def _dates(text: str) -> list[str]:
    found = []
    patterns = (
        r"\b([A-Z][a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(20\d{2}))?\b",
        r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Z][a-z]+)(?:\s+(20\d{2}))?\b",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            parts = match.groups()
            if parts[0].isdigit():
                day, month, year = parts
            else:
                month, day, year = parts
            if month.lower() not in MONTHS:
                continue
            year = year or str(datetime.now().year)
            value = f"{month.title()} {int(day)} {year}"
            if value not in found:
                found.append(value)
    return found[:2]


def _first_match(text: str, patterns: tuple[str, ...]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1)
    return ""


def _clean_place(value: str) -> str:
    cleaned = re.sub(r"\b(flight|flights|trip|ticket|tickets|date|dates|itinerary|planner)\b", " ", value, flags=re.I)
    cleaned = " ".join(cleaned.split()).strip(" .")
    for place in KNOWN_DESTINATIONS:
        if cleaned.casefold() == place.casefold():
            return place
    return cleaned.title() if cleaned.islower() else cleaned
