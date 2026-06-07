from __future__ import annotations

import re

from travel_parameters import extract_destination

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


def merged_parameters(original: str, model_parameters: object) -> dict[str, object]:
    merged: dict[str, object] = {}
    if isinstance(model_parameters, dict):
        for key, value in model_parameters.items():
            if value not in (None, ""):
                merged[str(key)] = value
    merged.update({key: value for key, value in extract_parameters(original).items() if value not in (None, "")})
    return merged


def extract_parameters(text: str) -> dict[str, object]:
    lowered = text.lower()
    params: dict[str, object] = {}
    destination = extract_destination(text)
    if destination:
        params["destination"] = destination
    count_pattern = r"\d{1,2}|" + "|".join(_COUNT_WORDS)
    days = re.search(rf"\b({count_pattern})\s*[- ]?\s*days?\b", lowered)
    if days:
        params["days"] = _count_value(days.group(1))
    people = re.search(
        rf"\b({count_pattern})\s*(?:people|person|persons|travelers|travellers|pax|adults?|guests?|packs?)\b",
        lowered,
    ) or re.search(
        rf"\b(?:number of people|people count|traveler count|traveller count|people|persons|pax|adults?)\s*(?:is|are|=|:|to)?\s*({count_pattern})\b",
        lowered,
    )
    if people:
        params["people_count"] = _count_value(people.group(1))
    params["food_focus"] = food_focus(lowered)
    return params


def infer_domain(original: str, kind: str, topic: str, parameters: dict[str, object], model_domain: str) -> str:
    model_domain = normalize_domain(model_domain)
    if model_domain and model_domain != "unknown":
        return model_domain
    lowered = f"{original} {topic}".lower()
    if kind == "pptx":
        return "presentation"
    if kind == "docx":
        if any(word in lowered for word in ("proposal", "pitch", "convince")):
            return "proposal"
        if any(word in lowered for word in ("guide", "setup", "configure", "troubleshoot", "router", "putty")):
            return "technical_guide"
        if any(word in lowered for word in ("research", "brief")):
            return "research_brief"
        return "travel_itinerary" if travel_signal(lowered, parameters) else "document"
    if kind != "xlsx":
        return "unknown"
    if any(word in lowered for word in ("household", "monthly", "home budget", "family budget")):
        return "household_budget"
    if any(word in lowered for word in ("compare", "comparison", "business", "proposal", "vendor", "supplier")):
        return "business_comparison"
    if food_focus(lowered) and travel_signal(lowered, parameters):
        return "travel_food_budget"
    if travel_signal(lowered, parameters) and any(word in lowered for word in ("budget", "cost", "spend", "spending", "expense", "tracker", "sheet", "excel")):
        return "travel_budget"
    if any(word in lowered for word in ("budget", "cost", "spend", "spending", "expense", "tracker")):
        return "generic_budget"
    return "generic_sheet"


def semantic_topic(kind: str, topic: str, domain: str, parameters: dict[str, object]) -> str:
    if kind != "xlsx" or domain not in {"travel_food_budget", "travel_budget"}:
        return topic
    destination = str(parameters.get("destination") or extract_destination(topic) or topic).strip()
    base = f"{destination} food budget tracker" if domain == "travel_food_budget" else f"{destination} travel budget"
    bits = [base]
    if parameters.get("days"):
        bits.append(f"for {parameters['days']} days")
    if parameters.get("people_count"):
        bits.append(f"for {parameters['people_count']} people")
    if domain == "travel_food_budget" and "restaurant" not in base.lower():
        bits.append("with restaurant detail")
    return " ".join(bits)


def enrich_artifact_topic(kind: str, topic: str, original: str) -> tuple[str, str, dict[str, object]]:
    parameters = merged_parameters(original, {})
    domain = infer_domain(original, kind, topic, parameters, "")
    return semantic_topic(kind, topic, domain, parameters), domain, parameters


def normalize_domain(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_]+", "_", str(value or "").lower()).strip("_")
    aliases = {
        "travel_food": "travel_food_budget",
        "food_trip_budget": "travel_food_budget",
        "food_budget": "travel_food_budget",
        "trip_budget": "travel_budget",
        "budget": "generic_budget",
        "sheet": "generic_sheet",
    }
    return aliases.get(cleaned, cleaned or "unknown")


def confidence(value: object) -> str:
    lowered = str(value or "").lower()
    return lowered if lowered in {"high", "medium", "low"} else "medium"


def food_focus(lowered: str) -> bool:
    return any(word in lowered for word in ("food", "restaurant", "restaurants", "meal", "meals", "dining", "cafe", "cafes", "eat", "eating", "foodie"))


def travel_signal(lowered: str, parameters: dict[str, object]) -> bool:
    if parameters.get("destination") or parameters.get("days") or parameters.get("people_count"):
        return True
    return any(word in lowered for word in ("trip", "travel", "holiday", "vacation", "flight", "hotel", "airbnb", "booking.com"))


def _count_value(raw: str) -> int:
    value = raw.lower().strip()
    return int(value) if value.isdigit() else _COUNT_WORDS.get(value, 1)
