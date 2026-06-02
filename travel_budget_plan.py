from __future__ import annotations

import re


def _parse_plan_updates(text: str) -> dict:
    lowered = text.lower()
    changes: dict[str, object] = {}
    days = re.search(r"\b(\d{1,2})\s*[- ]?\s*day\b", lowered)
    if days:
        changes["days"] = max(1, min(31, int(days.group(1))))
    people = re.search(r"\b(\d{1,2})\s+(?:people|person|persons|travellers|travelers|guests|adults)\b", lowered)
    if people:
        changes["people_count"] = max(1, min(20, int(people.group(1))))
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
    if any(word in lowered for word in ("middle", "mid range", "mid-range", "high end", "high-end", "4 star", "5 star", "guest favourite", "guest favorite")):
        changes["accommodation_preference"] = "middle to high-end; hotel 4-5 star or Airbnb guest favourite"
    destination = re.search(r"\b(?:to|in|for)\s+([A-Z][A-Za-z ,/]{2,50})(?:\s+from|\s+on|\s+for|\s+with|$)", text)
    if destination:
        value = " ".join(destination.group(1).split()).strip(" .,")
        if not re.search(r"\b(excel|budget|sheet|flight|hotel|airbnb|trip)\b", value, re.I):
            changes["destination"] = value
    destination = re.search(
        r"\b(?:for|to|in)\s+(?:a|an|the|my|our)?\s*(?:\d{1,2}\s*[- ]?\s*day\s+)?"
        r"([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})\s+"
        r"(?:food\s+)?(?:trip|holiday|vacation|travel)\b",
        text,
    )
    if destination:
        value = " ".join(destination.group(1).split()).strip(" .,")
        if not re.search(r"\b(excel|budget|tracker|sheet)\b", value, re.I):
            changes["destination"] = value
    leading_destination = re.search(
        r"^\s*(?:a|an|the|my|our)?\s*(?:\d{1,2}\s*[- ]?\s*day\s+)?"
        r"([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})\s+"
        r"(?:food\s+)?(?:trip|holiday|vacation|travel|budget\s+tracker)\b",
        text,
    )
    if leading_destination:
        value = " ".join(leading_destination.group(1).split()).strip(" .,")
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


def _template_request(text: str) -> bool:
    low = text.lower()
    return "template" in low or "travel sheet" in low or "specifically for travelling" in low or "travel purposes" in low


def _food_trip_request(text: str) -> bool:
    low = text.lower()
    return any(word in low for word in ("food trip", "restaurant", "restaurants", "eat", "eating", "foodie", "food highlights"))


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
