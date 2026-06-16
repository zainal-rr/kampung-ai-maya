from __future__ import annotations

"""Stay request parsing and provider URLs for Booking.com and Airbnb.

Context dates are only reused when the request matches the trip in the active
context; a request that names its own location never inherits stale trip dates.
A missing location is reported as missing instead of guessing a default city.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from urllib.parse import quote, urlencode

from maya_core.active_context_models import ActiveContext


# Context (an open itinerary or page) may only supply the stay location when
# the request actually points at it; otherwise a leftover browser page from a
# previous search would silently steal the location (the night1 Penang bug).
_TRIP_REFERENCE_RE = re.compile(r"\b(this trip|my trip|the trip|that trip|itinerary|same place|over there)\b", re.I)


@dataclass(frozen=True)
class StayDetails:
    location: str
    checkin: date
    checkout: date
    adults: int = 1
    children: int = 0
    rooms: int = 1
    assumptions: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()


def extract_stay_details(question: str, context: ActiveContext) -> StayDetails:
    context_text = "\n".join(
        part
        for part in (
            context.active_title,
            context.selected_content,
            context.nearby_context,
            context.document_context,
        )
        if part
    )
    joined = f"{question}\n{context_text}" if context_text else question
    assumptions = []
    missing = []
    question_location = _location(question, question)
    trip_reference = bool(_TRIP_REFERENCE_RE.search(question))
    location = question_location or (_location(question, joined) if trip_reference else "")
    if location and not question_location:
        assumptions.append(f"location {location} taken from the trip context you referenced")
    if not location:
        missing.append("location")
    question_dates = _dates(question)
    context_matches_location = bool(question_location) and bool(
        re.search(rf"\b{re.escape(question_location)}\b", context_text, re.I)
    )
    use_context_dates = bool(location) and (trip_reference or context_matches_location)
    dates = question_dates or (_dates(context_text) if use_context_dates else [])
    if not question_dates and dates:
        assumptions.append("dates taken from the active trip context because the request matches that trip")
    if not dates:
        checkin = date.today() + timedelta(days=14)
        checkout = checkin + timedelta(days=2)
        assumptions.append(
            f"dates {checkin.isoformat()} to {checkout.isoformat()} assumed two weeks out because no dates were given"
        )
    elif len(dates) == 1:
        checkin = dates[0]
        checkout = checkin + timedelta(days=1)
        assumptions.append("one night stay because only one date was provided")
    else:
        checkin, checkout = dates[0], dates[1]
    adults = _guests(question) or 1
    if "guest" not in question.lower() and "adult" not in question.lower() and "people" not in question.lower() and "person" not in question.lower():
        assumptions.append("1 adult because guests were not specified")
    return StayDetails(
        location=location,
        checkin=checkin,
        checkout=checkout,
        adults=adults,
        assumptions=tuple(assumptions),
        missing=tuple(missing),
    )


def stay_request_needs_active_context(question: str) -> bool:
    """Return True when the request explicitly points at an active itinerary/page."""
    return bool(_TRIP_REFERENCE_RE.search(question))


def booking_url(details: StayDetails) -> str:
    params = {
        "ss": details.location,
        "checkin": details.checkin.isoformat(),
        "checkout": details.checkout.isoformat(),
        "group_adults": str(details.adults),
        "group_children": str(details.children),
        "no_rooms": str(details.rooms),
        "selected_currency": "MYR",
    }
    return "https://www.booking.com/searchresults.html?" + urlencode(params)


def airbnb_url(details: StayDetails) -> str:
    params = {
        "checkin": details.checkin.isoformat(),
        "checkout": details.checkout.isoformat(),
        "adults": str(details.adults),
    }
    slug = quote(details.location.replace(",", " ").replace("  ", " ").strip().replace(" ", "-"))
    return f"https://www.airbnb.com/s/{slug}/homes?" + urlencode(params)


def extract_stay_options(text: str, limit: int = 5) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    options = []
    price_re = re.compile(r"\b(?:MYR|RM)\s*[\d,]+", re.I)
    noise = re.compile(r"^(filter|search|home|japan|kyoto|osaka|show price breakdown|free cancellation|popular filters|your budget)", re.I)
    for idx, line in enumerate(lines):
        if not price_re.search(line):
            continue
        if "–" in line or "-" in line and price_re.search(line):
            continue
        if any(marker in line.lower() for marker in ("budget", "filter", "per night", "popular", "review score")):
            continue
        before = []
        for prev in reversed(lines[max(0, idx - 8):idx]):
            if price_re.search(prev):
                break
            if noise.search(prev):
                continue
            before.append(prev)
            if len(before) >= 5:
                break
        context = list(reversed(before))[-5:]
        context = [item for item in context if not re.search(r"\bproperties found\b", item, re.I)]
        joined = " | ".join(context + [line])
        if joined and joined not in options:
            options.append(joined)
        if len(options) >= limit:
            break
    return options


def _location(question: str, joined: str) -> str:
    explicit = _first_match(question, (
        r"\bin\s+([A-Z][A-Za-z ,'-]{2,45})(?:\s+from|\s+on|\s+for|\s+with|$)",
        r"\bnear\s+([A-Z][A-Za-z ,'-]{2,45})(?:\s+from|\s+on|\s+for|\s+with|$)",
    ))
    if explicit:
        return _clean_location(explicit)
    for place in ("Kyoto", "Osaka", "Tokyo", "Penang", "Kuala Lumpur", "Bangkok", "Singapore"):
        if re.search(rf"\b{re.escape(place)}\b", joined, re.I):
            return place
    return ""


def _guests(text: str) -> int | None:
    match = re.search(r"\b(\d{1,2})\s+(?:guest|guests|adult|adults|people|person)\b", text, re.I)
    if not match:
        return None
    return max(1, min(16, int(match.group(1))))


def _dates(text: str) -> list[date]:
    found = []
    patterns = (
        r"\b([A-Z][a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(20\d{2}))?\b",
        r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Z][a-z]+)(?:\s+(20\d{2}))?\b",
        r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            parts = match.groups()
            try:
                if len(parts[0]) == 4 and parts[0].isdigit():
                    value = date(int(parts[0]), int(parts[1]), int(parts[2]))
                elif parts[0].isdigit():
                    day, month, year = parts
                    value = date(int(year or datetime.now().year), _month(month), int(day))
                else:
                    month, day, year = parts
                    value = date(int(year or datetime.now().year), _month(month), int(day))
            except (ValueError, TypeError, KeyError):
                continue
            if value not in found:
                found.append(value)
    return found[:2]


def _first_match(text: str, patterns: tuple[str, ...]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1)
    return ""


def _clean_location(value: str) -> str:
    cleaned = re.sub(r"\b(hotel|hotels|booking|airbnb|stay|room|rooms|apartment|home|homes)\b", " ", value, flags=re.I)
    return " ".join(cleaned.split()).strip(" .,")


def _month(value: str) -> int:
    key = value.lower()[:3]
    months = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
    return months[key]
