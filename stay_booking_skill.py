from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote, urlencode

from active_context import ActiveContextInspector
from active_context_models import ActiveContext
from browser_control import BrowserController
from browser_understanding import extract_browser_options_with_gemini
from permission_policy import action_permission
from storage import upsert_preference
from stay_booking_runtime import record_stay_skill, stay_reply, stay_workflow_value
from travel_budget import save_travel_plan_fields
from utils import OSBridge


BOOKING_SKILL_ID = "booking_com_hotel_search"
BOOKING_SKILL_NAME = "Booking.com Hotel Search"
AIRBNB_SKILL_ID = "airbnb_stay_search"
AIRBNB_SKILL_NAME = "Airbnb Stay Search"


@dataclass(frozen=True)
class StayDetails:
    location: str
    checkin: date
    checkout: date
    adults: int = 1
    children: int = 0
    rooms: int = 1
    assumptions: tuple[str, ...] = ()


@dataclass(frozen=True)
class StaySearchResult:
    provider: str
    url: str
    title: str
    visible_text: str
    details: StayDetails
    options: tuple[str, ...] = ()

    def verified(self) -> bool:
        text = f"{self.title}\n{self.visible_text}".lower()
        provider_ok = self.provider.lower().split(".")[0] in text or self.provider.lower() in (self.url or "").lower()
        location_ok = any(part.lower() in text or part.lower() in self.url.lower() for part in self.details.location.split() if len(part) >= 4)
        return provider_ok and location_ok


class BookingComHotelSkill:
    def __init__(self, db_path: str, bridge: OSBridge | None = None):
        self.db_path = db_path
        self.bridge = bridge or OSBridge()
        self.browser = BrowserController(self.bridge)
        self.inspector = ActiveContextInspector(db_path, self.bridge)

    async def run(self, question: str) -> str:
        if action_permission("travel_search") != "allow":
            return "I need your confirmation before searching hotels."
        await record_stay_skill(self.db_path, BOOKING_SKILL_ID, BOOKING_SKILL_NAME, "Search Booking.com with structured hotel parameters.", question)
        context = await self.inspector.inspect(question, allow_screen_fallback=False)
        details = extract_stay_details(question, context)
        await save_travel_plan_fields(
            self.db_path,
            destination=details.location,
            accommodation_type="hotel via Booking.com",
            people_count=details.adults,
            people_source="stay search request",
        )
        url = booking_url(details)
        result = await asyncio.to_thread(self._open_and_inspect, url, details, "Booking.com")
        if not result.options and result.visible_text:
            options = await extract_browser_options_with_gemini(
                self.db_path,
                provider="Booking.com",
                goal=f"hotel in {details.location} from {details.checkin} to {details.checkout}",
                page_title=result.title,
                page_url=result.url,
                page_text=result.visible_text,
            )
            if options:
                result = replace(result, options=tuple(options))
        await upsert_preference(self.db_path, "maya_active_workflow", stay_workflow_value("booking.com", details), source="skill")
        return stay_reply(result)

    def _open_and_inspect(self, url: str, details: StayDetails, provider: str) -> StaySearchResult:
        self.browser.open_new_tab_url(url)
        time.sleep(5.0)
        page = self.browser.inspect_page(12000)
        return StaySearchResult(provider, page.url or url, page.title, page.text, details, tuple(extract_stay_options(page.text)))


class AirbnbStaySkill:
    def __init__(self, db_path: str, bridge: OSBridge | None = None):
        self.db_path = db_path
        self.bridge = bridge or OSBridge()
        self.browser = BrowserController(self.bridge)
        self.inspector = ActiveContextInspector(db_path, self.bridge)

    async def run(self, question: str) -> str:
        if action_permission("travel_search") != "allow":
            return "I need your confirmation before searching Airbnb."
        await record_stay_skill(self.db_path, AIRBNB_SKILL_ID, AIRBNB_SKILL_NAME, "Search Airbnb with structured stay parameters.", question)
        context = await self.inspector.inspect(question, allow_screen_fallback=False)
        details = extract_stay_details(question, context)
        await save_travel_plan_fields(
            self.db_path,
            destination=details.location,
            accommodation_type="Airbnb",
            people_count=details.adults,
            people_source="stay search request",
        )
        url = airbnb_url(details)
        result = await asyncio.to_thread(self._open_and_inspect, url, details, "Airbnb")
        if not result.options and result.visible_text:
            options = await extract_browser_options_with_gemini(
                self.db_path,
                provider="Airbnb",
                goal=f"Airbnb in {details.location} from {details.checkin} to {details.checkout}",
                page_title=result.title,
                page_url=result.url,
                page_text=result.visible_text,
            )
            if options:
                result = replace(result, options=tuple(options))
        await upsert_preference(self.db_path, "maya_active_workflow", stay_workflow_value("airbnb", details), source="skill")
        return stay_reply(result)

    def _open_and_inspect(self, url: str, details: StayDetails, provider: str) -> StaySearchResult:
        self.browser.open_new_tab_url(url)
        time.sleep(5.0)
        page = self.browser.inspect_page(12000)
        return StaySearchResult(provider, page.url or url, page.title, page.text, details, tuple(extract_stay_options(page.text)))


async def run_booking_com_skill(db_path: str, question: str, *, bridge: OSBridge | None = None) -> str:
    return await BookingComHotelSkill(db_path, bridge).run(question)


async def run_airbnb_skill(db_path: str, question: str, *, bridge: OSBridge | None = None) -> str:
    return await AirbnbStaySkill(db_path, bridge).run(question)


def extract_stay_details(question: str, context: ActiveContext) -> StayDetails:
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
    assumptions = []
    location = _location(question, joined)
    if not location:
        location = "Kyoto"
        assumptions.append("location Kyoto because no location was explicit")
    dates = _dates(question) or _dates(joined)
    if not dates:
        checkin = date(2026, 8, 30)
        checkout = date(2026, 9, 4)
        assumptions.append("dates 2026-08-30 to 2026-09-04 from current Japan trip context")
    elif len(dates) == 1:
        checkin = dates[0]
        checkout = checkin + timedelta(days=1)
        assumptions.append("one night stay because only one date was provided")
    else:
        checkin, checkout = dates[0], dates[1]
    adults = _guests(question) or 1
    if "guest" not in question.lower() and "adult" not in question.lower() and "people" not in question.lower() and "person" not in question.lower():
        assumptions.append("1 adult because guests were not specified")
    return StayDetails(location=location, checkin=checkin, checkout=checkout, adults=adults, assumptions=tuple(assumptions))


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
            if price_re.search(prev) or noise.search(prev):
                continue
            before.append(prev)
            if len(before) >= 3:
                break
        after = [item for item in lines[idx + 1: idx + 4] if not noise.search(item)]
        joined = " | ".join(list(reversed(before)) + [line] + after)
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
            except (ValueError, TypeError):
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
