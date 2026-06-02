from __future__ import annotations

import asyncio
import time
from pathlib import Path

from active_context import ActiveContextInspector
from browser_control import BrowserController
from browser_understanding import extract_browser_options_with_gemini
from permission_policy import action_permission, contains_sensitive_info, hard_no_private_exposure_text
from skill_store import init_skill_db, record_skill_usage, upsert_skill
from storage import upsert_preference
from travel_budget import save_travel_plan_fields
from utils import OSBridge
from flight_search_models import FieldAttempt, FlightDetails
from flight_search_parsing import extract_flight_details
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
    def __init__(self, db_path: str, bridge: OSBridge | None = None):
        self.db_path = db_path
        self.bridge = bridge or OSBridge()
        self.browser = BrowserController(self.bridge)
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
        context = await self.inspector.inspect(question, allow_screen_fallback=False)
        details = extract_flight_details(question, context)
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
        await asyncio.to_thread(self.browser.open_new_tab_url, GOOGLE_FLIGHTS_URL)
        await asyncio.to_thread(time.sleep, 3.0)
        await asyncio.to_thread(self._close_active_overlay)
        await upsert_preference(self.db_path, "maya_active_workflow", _workflow_value(details), source="skill")
        if not fill:
            return _opened_reply(details)
        attempts = await asyncio.to_thread(self._fill_verify_and_search, details)
        if not self.last_price_options and self.last_result_text:
            self.last_price_options = await extract_browser_options_with_gemini(
                self.db_path,
                provider="Google Flights",
                goal=f"{details.origin} to {details.destination} on {details.depart}",
                page_title=self.last_result_title,
                page_url=self.last_result_url,
                page_text=self.last_result_text,
            )
        return _filled_reply(details, attempts, self.last_price_options, self.last_result_page)

    def _fill_verify_and_search(self, details: FlightDetails) -> list[FieldAttempt]:
        self._close_active_overlay()
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
        finalized = self._finalize_attempts(details, attempts)
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
            if current_after == "one way" and "Return" not in [label for label in self._field_labels()]:
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
            clicked = self.browser.click_exact_text_last("Search")
            if clicked == "NOT_FOUND":
                clicked = self.browser.click_visible_text("Search")
            if clicked == "NOT_FOUND":
                page = self.browser.inspect_page(8000)
                self.last_result_page = f"{page.title} | {page.url}"
                self.last_result_title = page.title
                self.last_result_url = page.url
                self.last_result_text = page.text
                return FieldAttempt("results", "Search", "not verified", "Search button not found; did not click Explore fallback")
            time.sleep(8.0)
            page = self.browser.inspect_page(8000)
            self.last_result_page = f"{page.title} | {page.url}"
            self.last_result_title = page.title
            self.last_result_url = page.url
            self.last_result_text = page.text
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
        before = self._field_labels({"input"})
        if _labels_contain(before, value):
            return FieldAttempt(field, value, "already set")
        try:
            self._close_active_overlay()
            if select_suggestion:
                filled = self.browser.fill_field(target, value)
                time.sleep(0.65)
                self.bridge.press_shortcut("down")
                time.sleep(0.2)
                self.bridge.press_shortcut("return")
                time.sleep(0.9)
                labels = self._field_labels({"input"})
                if _labels_contain(labels, value):
                    return FieldAttempt(field, value, "verified", f"{filled}; keyboard selected")
                selected = self.browser.click_visible_text(value)
                time.sleep(0.9)
                labels = self._field_labels({"input"})
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
            labels = self._field_labels({"input"})
            if _labels_contain(labels, value) or _date_verified(labels, value):
                return FieldAttempt(field, value, "verified")
            return FieldAttempt(field, value, "not verified", clicked)
        except Exception as exc:
            if required:
                return FieldAttempt(field, value, "failed", str(exc))
            return FieldAttempt(field, value, "skipped", str(exc))

    def _field_labels(self, kinds: set[str] | None = None) -> list[str]:
        allowed = kinds or {"input", "button"}
        return [item.label for item in self.browser.inspect_elements(120) if item.kind in allowed]

    def _close_active_overlay(self) -> None:
        try:
            self.bridge.press_shortcut("escape")
            time.sleep(0.35)
        except Exception:
            pass
        try:
            self.browser.click_visible_text("Done")
            time.sleep(0.45)
        except Exception:
            pass

    def _finalize_attempts(self, details: FlightDetails, attempts: list[FieldAttempt]) -> list[FieldAttempt]:
        input_labels = self._field_labels({"input"})
        final = []
        for attempt in attempts:
            if attempt.field in {"origin", "destination"}:
                ok = _labels_contain(input_labels, attempt.value)
            elif attempt.field in {"departure", "return"}:
                ok = _date_verified(input_labels, attempt.value)
            else:
                if attempt.field == "trip type":
                    page = self.browser.inspect_page(1000).text
                    expected = "one way" if details.one_way else "round trip"
                    ok = _current_trip_type(page) == expected
                else:
                    ok = attempt.status in {"verified", "already set"}
            if ok:
                final.append(attempt if attempt.status in {"verified", "already set"} else FieldAttempt(attempt.field, attempt.value, "verified", "final state"))
            elif attempt.status == "skipped":
                final.append(attempt)
            else:
                final.append(FieldAttempt(attempt.field, attempt.value, "not verified", "not visible in final browser state"))
        return final

    async def _record_skill(self, question: str) -> None:
        await init_skill_db(self.db_path)
        scaffold = Path(__file__).resolve().parent / "maya_skills" / "active" / "flight_search.md"
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
