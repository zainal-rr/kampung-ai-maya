from __future__ import annotations

import asyncio
import time
from pathlib import Path

from active_context import ActiveContextInspector
from active_context_models import ActiveContext
from browser_driver import make_browser_controller
from browser_observe import wait_for_content
from flight_search_deeplink import is_extension_driver, note_flight_intent, run_flight_deep_link
from browser_understanding import extract_browser_options_with_gemini, grounded_browser_options
from maya_core.repo_paths import repo_root
from permission_policy import action_permission, contains_sensitive_info, hard_no_private_exposure_text
from skill_store import init_skill_db, record_skill_usage, upsert_skill
from storage import upsert_preference
from travel_budget import save_travel_plan_fields
from utils import OSBridge
from flight_search_models import FieldAttempt, FlightDetails
from flight_search_parsing import extract_flight_details, flight_request_needs_active_context
from flight_search_form_helpers import capture_result_page, close_active_overlay, field_labels, finalize_attempts
from flight_search_reply import (
    _clarification_reply,
    _current_trip_type,
    _date_verified,
    _filled_reply,
    _labels_contain,
    _opened_reply,
    _ready_for_search,
    _unverified_required_fields,
    _workflow_value,
    extract_date_grid_price,
    extract_flight_options,
)


GOOGLE_FLIGHTS_URL = "https://www.google.com/travel/flights"
SKILL_ID = "travel_research"
SKILL_NAME = "Travel Research"


class FlightSearchSkill:
    RESULT_WAIT_TIMEOUT = 25.0
    RESULT_MARKERS = ("Nonstop", "Sorted by", "results returned", "Top departing", "No results")

    def __init__(self, db_path: str, bridge: OSBridge | None = None):
        self.db_path = db_path
        self.bridge = bridge or OSBridge()
        self.browser = make_browser_controller(bridge)
        self.inspector = ActiveContextInspector(db_path, self.bridge)
        self.last_price_options: list[str] = []
        self.last_result_page = ""
        self.last_result_title = ""
        self.last_result_url = ""
        self.last_result_text = ""

    async def run(self, question: str, *, fill: bool = True) -> str:
        if action_permission("travel_search") != "allow":
            return "I need your confirmation before searching flights."
        await self._record_skill(question)
        context = await self._request_context(question)
        details = extract_flight_details(question, context)
        note_flight_intent(details)
        if details.missing:
            await upsert_preference(self.db_path, "maya_active_workflow", _workflow_value(details), source="skill")
            return _clarification_reply(details)
        await save_travel_plan_fields(
            self.db_path,
            origin=details.origin,
            destination=details.destination,
            departure_date=details.depart,
            return_date=details.return_date,
            flight_trip_type="one way" if details.one_way else "return",
        )
        if is_extension_driver(self.browser):
            # The extension cannot simulate autocomplete keyboards; the
            # validated deep link lands directly on the results page instead.
            return await run_flight_deep_link(self, details)
        await asyncio.to_thread(self.browser.open_new_tab_url, GOOGLE_FLIGHTS_URL)
        await asyncio.to_thread(time.sleep, 3.0)
        await asyncio.to_thread(close_active_overlay, self.browser, self.bridge)
        await upsert_preference(self.db_path, "maya_active_workflow", _workflow_value(details), source="skill")
        if not fill:
            return _opened_reply(details)
        attempts = await asyncio.to_thread(self._fill_verify_and_search, details)
        if not self.last_price_options and self.last_result_text:
            gemini_options = await extract_browser_options_with_gemini(
                self.db_path,
                provider="Google Flights",
                goal=f"{details.origin} to {details.destination} on {details.depart}",
                page_title=self.last_result_title,
                page_url=self.last_result_url,
                page_text=self.last_result_text,
            )
            self.last_price_options = grounded_browser_options(gemini_options, self.last_result_text)
        return _filled_reply(details, attempts, self.last_price_options, self.last_result_page)

    async def _request_context(self, question: str) -> ActiveContext:
        if is_extension_driver(self.browser) and not flight_request_needs_active_context(question):
            return ActiveContext(app="Google Chrome", selection_type="none", source="request_only")
        return await self.inspector.inspect(question, allow_screen_fallback=False)

    def _fill_verify_and_search(self, details: FlightDetails) -> list[FieldAttempt]:
        close_active_overlay(self.browser, self.bridge)
        attempts = []
        if details.one_way:
            attempts.append(self._set_one_way())
        else:
            attempts.append(self._set_round_trip())
        attempts.extend([
            self._attempt_field("origin", "Federal Territory of Kuala Lumpur", details.origin, required=False, select_suggestion=True),
            self._attempt_field("destination", "Where to?", details.destination, required=True, press_return=True, select_suggestion=True),
            self._attempt_field("departure", "Departure", details.depart, required=True, press_return=True),
        ])
        if details.return_date:
            attempts.append(self._attempt_field("return", "Return", details.return_date, required=False, press_return=True))
        finalized = finalize_attempts(self, details, attempts)
        finalized.append(self._click_search_and_collect(details, finalized))
        return finalized

    def _set_one_way(self) -> FieldAttempt:
        page = self.browser.inspect_page(1000).text
        current = _current_trip_type(page)
        if current == "one way":
            return FieldAttempt("trip type", "one way", "already set")
        try:
            opened = self.browser.click_visible_text("Round trip")
            if opened == "NOT_FOUND":
                opened = self.browser.click_visible_text("One way")
            time.sleep(0.4)
            selected = self.browser.click_visible_text("One way")
            time.sleep(0.7)
            page_after = self.browser.inspect_page(1200).text
            current_after = _current_trip_type(page_after)
            if current_after == "one way" and "Return" not in [label for label in field_labels(self.browser)]:
                return FieldAttempt("trip type", "one way", "verified", f"{opened}; {selected}")
            if current_after == "one way":
                return FieldAttempt("trip type", "one way", "verified", f"{opened}; {selected}")
            return FieldAttempt("trip type", "one way", "not verified", f"{opened}; {selected}; current={current_after or 'unknown'}")
        except Exception as exc:
            return FieldAttempt("trip type", "one way", "failed", str(exc))

    def _set_round_trip(self) -> FieldAttempt:
        page = self.browser.inspect_page(1000).text
        current = _current_trip_type(page)
        if current == "round trip":
            return FieldAttempt("trip type", "round trip", "already set")
        try:
            opened = self.browser.click_visible_text("One way")
            if opened == "NOT_FOUND":
                opened = self.browser.click_visible_text("Round trip")
            time.sleep(0.4)
            selected = self.browser.click_visible_text("Round trip")
            time.sleep(0.7)
            page_after = self.browser.inspect_page(1200).text
            if _current_trip_type(page_after) == "round trip":
                return FieldAttempt("trip type", "round trip", "verified", f"{opened}; {selected}")
            return FieldAttempt("trip type", "round trip", "not verified", f"{opened}; {selected}")
        except Exception as exc:
            return FieldAttempt("trip type", "round trip", "failed", str(exc))

    def _click_search_and_collect(self, details: FlightDetails, attempts: list[FieldAttempt]) -> FieldAttempt:
        if not _ready_for_search(details, attempts):
            missing = _unverified_required_fields(details, attempts)
            return FieldAttempt("results", "Search", "skipped", "required fields not verified: " + ", ".join(missing))
        try:
            close_active_overlay(self.browser, self.bridge)
            clicked = self.browser.click_exact_text_last("Search")
            if clicked == "NOT_FOUND":
                clicked = self.browser.click_visible_text("Search")
            if clicked == "NOT_FOUND":
                capture_result_page(self, self.browser.inspect_page(14000))
                return FieldAttempt("results", "Search", "not verified", "Search button not found; did not click Explore fallback")
            readiness = wait_for_content(
                self.browser,
                min_chars=1200,
                require_any=self.RESULT_MARKERS,
                timeout_seconds=self.RESULT_WAIT_TIMEOUT,
                stable_seconds=1.0,
                max_chars=14000,
            )
            page = readiness.page if readiness.page.url else self.browser.inspect_page(14000)
            capture_result_page(self, page)
            self.last_price_options = extract_flight_options(page.text, details.destination, details.depart)
            if not self.last_price_options:
                grid_price = extract_date_grid_price(page.text, details.depart)
                if grid_price:
                    self.last_price_options = [grid_price]
            if self.last_price_options:
                return FieldAttempt("results", "Search", "verified", clicked)
            if "google.com/travel/explore" in page.url:
                return FieldAttempt("results", "Search", "not verified", "unexpectedly landed on Explore after Search click")
            return FieldAttempt("results", "Search", "not verified", clicked)
        except Exception as exc:
            return FieldAttempt("results", "Search", "failed", str(exc))

    def _attempt_field(
        self,
        field: str,
        target: str,
        value: str,
        *,
        required: bool,
        press_return: bool = False,
        select_suggestion: bool = False,
    ) -> FieldAttempt:
        if not value:
            return FieldAttempt(field, value, "skipped", "no value")
        if contains_sensitive_info(value):
            return FieldAttempt(field, "", "blocked", hard_no_private_exposure_text())
        before = field_labels(self.browser, {"input"})
        if _labels_contain(before, value):
            return FieldAttempt(field, value, "already set")
        try:
            close_active_overlay(self.browser, self.bridge)
            if select_suggestion:
                filled = self.browser.fill_field(target, value)
                time.sleep(0.65)
                self.bridge.press_shortcut("down")
                time.sleep(0.2)
                self.bridge.press_shortcut("return")
                time.sleep(0.9)
                labels = field_labels(self.browser, {"input"})
                if _labels_contain(labels, value):
                    return FieldAttempt(field, value, "verified", f"{filled}; keyboard selected")
                selected = self.browser.click_visible_text(value)
                time.sleep(0.9)
                labels = field_labels(self.browser, {"input"})
                if _labels_contain(labels, value):
                    return FieldAttempt(field, value, "verified", f"{filled}; fallback clicked {selected}")
                if filled != "NOT_FOUND" or selected != "NOT_FOUND":
                    return FieldAttempt(field, value, "not verified", f"{filled}; keyboard select failed; {selected}")
            clicked = self.browser.click_text(target)
            time.sleep(0.35)
            self.bridge.press_shortcut("cmd+a")
            self.bridge.type_text(value)
            time.sleep(0.65)
            if select_suggestion:
                self.bridge.press_shortcut("down")
                time.sleep(0.25)
            if press_return:
                self.bridge.press_shortcut("return")
                time.sleep(1.0)
            labels = field_labels(self.browser, {"input"})
            if _labels_contain(labels, value) or _date_verified(labels, value):
                return FieldAttempt(field, value, "verified")
            return FieldAttempt(field, value, "not verified", clicked)
        except Exception as exc:
            if required:
                return FieldAttempt(field, value, "failed", str(exc))
            return FieldAttempt(field, value, "skipped", str(exc))

    async def _record_skill(self, question: str) -> None:
        await init_skill_db(self.db_path)
        scaffold = repo_root(__file__) / "maya_skills" / "active" / "flight_search.md"
        await upsert_skill(
            self.db_path,
            skill_id=SKILL_ID,
            name=SKILL_NAME,
            description="Open Google Flights, extract flight fields from active itinerary context, fill fields one by one, and verify before claiming success.",
            safety="bounded",
            approval_mode="policy_guard",
            status="active",
            source="local",
            scaffold_path=str(scaffold),
        )
        await record_skill_usage(
            self.db_path,
            skill_id=SKILL_ID,
            name=SKILL_NAME,
            query=question,
            lane="iMac flight_search_skill",
            reason="flight intent routed to executable skill",
        )


async def run_flight_search_skill(db_path: str, question: str, *, fill: bool = True, bridge: OSBridge | None = None) -> str:
    return await FlightSearchSkill(db_path, bridge).run(question, fill=fill)
