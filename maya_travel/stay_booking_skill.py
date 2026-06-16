from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, replace

from active_context import ActiveContextInspector
from active_context_models import ActiveContext
from browser_control import note_browser_intent
from browser_driver import make_browser_controller
from browser_understanding import extract_browser_options_with_gemini, grounded_browser_options
from permission_policy import action_permission
from storage import upsert_preference
from stay_booking_parsing import (  # noqa: F401 - re-exported for existing callers
    StayDetails,
    airbnb_url,
    booking_url,
    extract_stay_details,
    extract_stay_options,
    stay_request_needs_active_context,
)
from stay_booking_runtime import record_stay_skill, stay_reply, stay_workflow_value
from travel_budget import save_travel_plan_fields
from utils import OSBridge


BOOKING_SKILL_ID = "booking_com_hotel_search"
BOOKING_SKILL_NAME = "Booking.com Hotel Search"
AIRBNB_SKILL_ID = "airbnb_stay_search"
AIRBNB_SKILL_NAME = "Airbnb Stay Search"


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
        self.browser = make_browser_controller(bridge)
        self.inspector = ActiveContextInspector(db_path, self.bridge)

    async def run(self, question: str) -> str:
        if action_permission("travel_search") != "allow":
            return "I need your confirmation before searching hotels."
        await record_stay_skill(self.db_path, BOOKING_SKILL_ID, BOOKING_SKILL_NAME, "Search Booking.com with structured hotel parameters.", question)
        context = await _request_context(self.browser, self.inspector, question)
        details = extract_stay_details(question, context)
        _note_stay_intent(details)
        if details.missing:
            return _stay_clarification_reply("Booking.com", details)
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
            options = grounded_browser_options(options, result.visible_text)
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
        self.browser = make_browser_controller(bridge)
        self.inspector = ActiveContextInspector(db_path, self.bridge)

    async def run(self, question: str) -> str:
        if action_permission("travel_search") != "allow":
            return "I need your confirmation before searching Airbnb."
        await record_stay_skill(self.db_path, AIRBNB_SKILL_ID, AIRBNB_SKILL_NAME, "Search Airbnb with structured stay parameters.", question)
        context = await _request_context(self.browser, self.inspector, question)
        details = extract_stay_details(question, context)
        _note_stay_intent(details)
        if details.missing:
            return _stay_clarification_reply("Airbnb", details)
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
            options = grounded_browser_options(options, result.visible_text)
            if options:
                result = replace(result, options=tuple(options))
        await upsert_preference(self.db_path, "maya_active_workflow", stay_workflow_value("airbnb", details), source="skill")
        return stay_reply(result)

    def _open_and_inspect(self, url: str, details: StayDetails, provider: str) -> StaySearchResult:
        self.browser.open_new_tab_url(url)
        time.sleep(5.0)
        page = self.browser.inspect_page(12000)
        return StaySearchResult(provider, page.url or url, page.title, page.text, details, tuple(extract_stay_options(page.text)))


def _stay_clarification_reply(provider: str, details: StayDetails) -> str:
    questions = []
    if "location" in details.missing:
        questions.append("Where should I search for the stay?")
    return "\n".join(
        line
        for line in (
            f"{provider} search needs one detail before I open the browser.",
            f"missing: {', '.join(details.missing)}",
            " ".join(questions),
        )
        if line
    )


async def _request_context(browser, inspector: ActiveContextInspector, question: str) -> ActiveContext:
    if getattr(browser, "DRIVER", "") == "extension" and not stay_request_needs_active_context(question):
        return ActiveContext(app="Google Chrome", selection_type="none", source="request_only")
    return await inspector.inspect(question, allow_screen_fallback=False)


def _note_stay_intent(details: StayDetails) -> None:
    note_browser_intent(
        {
            "location": details.location,
            "checkin": details.checkin.isoformat(),
            "checkout": details.checkout.isoformat(),
            "adults": details.adults,
            "missing": ", ".join(details.missing),
        }
    )


async def run_booking_com_skill(db_path: str, question: str, *, bridge: OSBridge | None = None) -> str:
    return await BookingComHotelSkill(db_path, bridge).run(question)


async def run_airbnb_skill(db_path: str, question: str, *, bridge: OSBridge | None = None) -> str:
    return await AirbnbStaySkill(db_path, bridge).run(question)
