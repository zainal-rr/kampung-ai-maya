from __future__ import annotations

import re

_COUNT_WORDS = {
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
}
_COUNT_PATTERN = r"\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten"


def _parse_plan_updates(text: str) -> dict:
    lowered = text.lower()
    changes: dict[str, object] = {}
    days = re.search(rf"\b({_COUNT_PATTERN})\s*[- ]?\s*days?\b", lowered)
    if days:
        changes["days"] = max(1, min(31, _count_value(days.group(1))))
    people = re.search(rf"\b({_COUNT_PATTERN})\s+(?:people|person|persons|travellers|travelers|guest|guests|adult|adults|pax|pack|packs)\b", lowered)
    if not people:
        people = re.search(
            rf"\b(?:number of people|people count|traveler count|traveller count|people|persons|guests|adults|pax)\s*(?:is|are|=|:)?\s*({_COUNT_PATTERN})\b",
            lowered,
        )
    if people:
        changes["people_count"] = max(1, min(20, _count_value(people.group(1))))
        changes["people_source"] = "explicit user request"
    if "cheapest" in lowered:
        changes["flight_preference"] = "cheapest"
    elif any(word in lowered for word in ("morning", "early flight")):
        changes["flight_preference"] = "morning schedule"
    elif any(word in lowered for word in ("night", "evening", "late flight")):
        changes["flight_preference"] = "night schedule"
    elif "nonstop" in lowered or "direct flight" in lowered:
        changes["flight_preference"] = "nonstop/direct"
    if "hotel" in lowered or "booking.com" in lowered:
        changes["accommodation_type"] = "hotel via Booking.com"
    if "airbnb" in lowered:
        changes["accommodation_type"] = "Airbnb"
    changes.update(_parse_price_mentions(text))
    if any(word in lowered for word in ("middle", "mid range", "mid-range", "high end", "high-end", "4 star", "5 star", "guest favourite", "guest favorite")):
        changes["accommodation_preference"] = "middle to high-end; hotel 4-5 star or Airbnb guest favourite"
    destination = re.search(r"\b(?:to|in|for)\s+([A-Z][A-Za-z ,/]{2,50}?)(?:\s+from|\s+on|\s+for|\s+with|\s+and\s+for|\s+and\s+with|$)", text)
    if destination:
        value = _clean_destination_value(destination.group(1))
        if not re.search(r"\b(excel|budget|sheet|flight|hotel|airbnb|trip)\b", value, re.I):
            changes["destination"] = value
    destination = re.search(
        r"\b(?:for|to|in)\s+(?:a|an|the|my|our)?\s*(?:\d{1,2}\s*[- ]?\s*day\s+)?"
        r"([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})\s+"
        r"(?:food\s+)?(?:trip|holiday|vacation|travel)\b",
        text,
    )
    if destination:
        value = _clean_destination_value(destination.group(1))
        if not re.search(r"\b(excel|budget|tracker|sheet)\b", value, re.I):
            changes["destination"] = value
    leading_destination = re.search(
        r"^\s*(?:a|an|the|my|our)?\s*(?:\d{1,2}\s*[- ]?\s*day\s+)?"
        r"([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})\s+"
        r"(?:food\s+)?(?:trip|holiday|vacation|travel|budget\s+tracker)\b",
        text,
    )
    if leading_destination:
        value = _clean_destination_value(leading_destination.group(1))
        if not re.search(r"\b(excel|budget|tracker|sheet|travel)\b", value, re.I):
            changes["destination"] = value
    if "destination" not in changes:
        lowered = lowered.strip()
        known_destinations = ("seoul", "tokyo", "kyoto", "osaka", "bangkok", "singapore", "taipei", "hong kong")
        for place in known_destinations:
            if re.search(rf"\b{re.escape(place)}\b", lowered):
                changes["destination"] = place.title()
                break
    return changes


def _count_value(raw: str) -> int:
    value = raw.strip().lower()
    if value.isdigit():
        return int(value)
    return _COUNT_WORDS.get(value, 1)


def _clean_destination_value(raw: str) -> str:
    value = " ".join(str(raw or "").split()).strip(" .,")
    value = re.sub(r"\s+\b(?:and|also)\b$", "", value, flags=re.I).strip(" .,")
    value = re.sub(
        r"\s+\b(?:food|foods|meal|meals|mill|mills|mail|mails|restaurant|restaurants|dining|cafe|cafes|budget|budgets|tracker|tracking|expense|expenses|cost|costs|spend|spending|spreadsheet|sheet|excel|xlsx|workbook|plan)\b.*$",
        "",
        value,
        flags=re.I,
    ).strip(" .,")
    return value


def _parse_price_mentions(text: str) -> dict:
    changes: dict[str, object] = {}
    price_specs = (
        ("stay_price_airbnb_myr", "Airbnb", r"airbnb"),
        ("stay_price_booking_myr", "Booking.com hotel", r"booking\.com|hotel"),
        ("selected_stay_price_myr", "selected stay", r"accommodation|stay"),
        ("selected_flight_price_myr", "flight", r"flight|flights|airfare|air\s*ticket"),
    )
    stay_options: list[str] = []
    for key, provider, label_pattern in price_specs:
        amount = _first_price_for_label(text, label_pattern)
        if amount is None:
            continue
        changes[key] = amount
        if key == "selected_flight_price_myr":
            changes.setdefault("flight_preference", "selected flight price provided by user")
        else:
            stay_options.append(f"{provider}: MYR {amount}")
            if "selected_stay_price_myr" not in changes or key != "selected_stay_price_myr":
                changes["selected_stay_price_myr"] = amount
                changes["selected_stay_provider"] = provider
                changes["accommodation_type"] = provider
    if stay_options:
        changes["stay_price_notes"] = "; ".join(stay_options)
    return changes


def _first_price_for_label(text: str, label_pattern: str) -> int | float | None:
    patterns = (
        rf"\b(?:{label_pattern})\b[^.,;\n]{{0,40}}?(?:rm|myr)\s*(?P<amount>\d[\d,]*(?:\.\d+)?)",
        rf"(?:rm|myr)\s*(?P<amount>\d[\d,]*(?:\.\d+)?)[^.,;\n]{{0,30}}?\b(?:{label_pattern})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return _price_value(match.group("amount"))
    return None


def _price_value(raw: str) -> int | float | None:
    try:
        value = float(raw.replace(",", ""))
    except ValueError:
        return None
    if value <= 0:
        return None
    return int(value) if value.is_integer() else round(value, 2)


def _template_request(text: str) -> bool:
    low = text.lower()
    return (
        "template" in low
        or "travel sheet" in low
        or "travel budget excel" in low
        or "travel budget spreadsheet" in low
        or "travel budget sheet" in low
        or "travel budget workbook" in low
        or "specifically for travelling" in low
        or "travel purposes" in low
    )


def _food_trip_request(text: str) -> bool:
    low = text.lower()
    food_markers = (
        "food",
        "food trip",
        "food budget",
        "food tracker",
        "restaurant",
        "restaurants",
        "meal",
        "meals",
        "mill",
        "mills",
        "mail",
        "mails",
        "dining",
        "cafe",
        "cafes",
        "eat",
        "eating",
        "foodie",
        "food highlights",
    )
    return any(word in low for word in food_markers)


def _trip_specific_request(text: str, parsed: dict) -> bool:
    low = text.lower()
    if _current_trip_reference(text):
        return True
    if parsed.get("destination") or parsed.get("departure_date") or parsed.get("return_date"):
        return True
    if re.search(r"\bto\s+[A-Z][A-Za-z ,/]{2,50}\b", text):
        return True
    if re.search(r"\b(?:for|in)\s+(?:a|an|the|my|our)?\s*(?:\d{1,2}\s*[- ]?\s*day\s+)?[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3}\s+(?:food\s+)?(?:trip|holiday|vacation|travel)\b", text):
        return True
    return False


def _current_trip_reference(text: str) -> bool:
    low = text.lower()
    explicit = (
        "this trip",
        "my trip",
        "our trip",
        "current trip",
        "for the trip",
        "for my travel",
        "for our travel",
        "use the trip",
        "use current",
    )
    return any(phrase in low for phrase in explicit)


def _template_plan() -> dict:
    return {
        "origin": "",
        "destination": "",
        "departure_date": "",
        "return_date": "",
        "flight_preference": "",
        "accommodation_type": "",
        "accommodation_preference": "middle to high-end by default; hotels 4-5 star or Airbnb guest favourite when planning a real trip",
        "people_count": "",
        "people_source": "enter manually",
        "template_mode": True,
    }


def _plan_reply(plan: dict, changes: dict, party: TravelParty) -> str:
    lines = ["Travel plan memory updated."]
    if changes:
        lines.append("Saved:")
        lines.extend(f"- {key}: {value}" for key, value in changes.items())
    else:
        lines.append("No new parameter was detected, so I kept the existing plan.")
    lines.append(f"Travelers: {plan.get('people_count', party.count)} ({plan.get('people_source', party.source)})")
    if not plan.get("flight_preference"):
        lines.append("Next: Which flight should I keep: cheapest, morning schedule, night schedule, or a specific option?")
    elif not plan.get("accommodation_type"):
        lines.append("Next: Hotel on Booking.com or Airbnb?")
    return "\n".join(lines)
