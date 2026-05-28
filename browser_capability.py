from __future__ import annotations

from dataclasses import dataclass

from browser_skill import run_browser_skill
from flight_search_skill import run_flight_search_skill
from stay_booking_skill import run_airbnb_skill, run_booking_com_skill
from utils import OSBridge


@dataclass(frozen=True)
class BrowserCapabilityRoute:
    child_skill: str
    reason: str


async def run_browser_capability(db_path: str, request: str, *, bridge: OSBridge | None = None) -> str:
    route = route_browser_capability(request)
    if route.child_skill == "flight_search":
        return await run_flight_search_skill(db_path, request, fill=True, bridge=bridge)
    if route.child_skill == "airbnb_stay_search":
        return await run_airbnb_skill(db_path, request, bridge=bridge)
    if route.child_skill == "booking_com_hotel_search":
        return await run_booking_com_skill(db_path, request, bridge=bridge)
    return await run_browser_skill(db_path, request, bridge=bridge)


def route_browser_capability(request: str) -> BrowserCapabilityRoute:
    lowered = request.lower()
    if "flight" in lowered or "flights" in lowered:
        return BrowserCapabilityRoute("flight_search", "flight keyword")
    if "airbnb" in lowered:
        return BrowserCapabilityRoute("airbnb_stay_search", "Airbnb keyword")
    if any(word in lowered for word in ("booking.com", "hotel", "hotels", "room", "rooms", "accommodation")):
        return BrowserCapabilityRoute("booking_com_hotel_search", "hotel or accommodation keyword")
    if any(marker in lowered for marker in ("google image", "google images", "image search", "search images", "find images")):
        return BrowserCapabilityRoute("google_images", "image search marker")
    return BrowserCapabilityRoute("general_browser", "general browser request")


def browser_child_skill_catalog() -> list[dict[str, str]]:
    return [
        {
            "id": "general_browser",
            "owner": "local browser control",
            "role": "Open Chrome, Google search, inspect pages, click safe targets, and fill non-sensitive fields.",
        },
        {
            "id": "google_images",
            "owner": "local browser control",
            "role": "Open Google Images directly for visual reference searches.",
        },
        {
            "id": "flight_search",
            "owner": "local browser control + Gemini when itinerary/page understanding is needed",
            "role": "Open Google Flights, fill structured flight fields, read prices, and stop before booking/payment.",
        },
        {
            "id": "booking_com_hotel_search",
            "owner": "local browser control + Gemini when hotel comparison needs page understanding",
            "role": "Open Booking.com with structured stay fields, prefer mid-to-high range hotels, and stop before booking/payment.",
        },
        {
            "id": "airbnb_stay_search",
            "owner": "local browser control + Gemini when listing comparison needs page understanding",
            "role": "Open Airbnb with structured stay fields, prefer Guest Favourite when visible, and stop before reserve/payment.",
        },
    ]
