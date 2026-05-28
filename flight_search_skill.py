from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from active_context import ActiveContextInspector
from active_context_models import ActiveContext
from browser_control import BrowserController
from browser_understanding import extract_browser_options_with_gemini
from permission_policy import action_permission, contains_sensitive_info, hard_no_private_exposure_text
from skill_store import init_skill_db, record_skill_usage, upsert_skill
from storage import upsert_preference
from travel_budget import save_travel_plan_fields
from utils import OSBridge


GOOGLE_FLIGHTS_URL = "https://www.google.com/travel/flights"
SKILL_ID = "travel_research"
SKILL_NAME = "Travel Research"


@dataclass(frozen=True)
class FlightDetails:
    origin: str
    destination: str
    depart: str
    return_date: str = ""
    one_way: bool = True
    missing: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()


@dataclass(frozen=True)
class FieldAttempt:
    field: str
    value: str
    status: str
    detail: str = ""

    def line(self) -> str:
        suffix = f" ({self.detail})" if self.detail else ""
        return f"{self.field}: {self.status} {self.value}{suffix}".strip()


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
        destination = "Osaka"
        assumptions.append("destination Osaka because no destination was explicit")
    if not dates:
        if use_context_dates:
            dates = ["August 30 2026"]
            assumptions.append("departure August 30 2026 from current Japan trip context")
        else:
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


def _labels_contain(labels: list[str], value: str) -> bool:
    low = value.lower()
    tokens = [token for token in re.split(r"\W+", low) if len(token) >= 3]
    return any(low in label.lower() or (tokens and all(token in label.lower() for token in tokens[:2])) for label in labels)


def _date_verified(labels: list[str], value: str) -> bool:
    parts = value.split()
    if len(parts) < 2:
        return False
    month = parts[0][:3].lower()
    if not parts[1].isdigit():
        return False
    day = str(int(parts[1]))
    return any(month in label.lower() and day in label for label in labels)


def _current_trip_type(page_text: str) -> str:
    compact = "\n".join(line.strip() for line in page_text.splitlines() if line.strip())
    match = re.search(r"\bFlights\s*\n\s*(One way|Round trip)\b", compact, re.I)
    if match:
        return match.group(1).lower()
    lines = compact.splitlines()
    for idx, line in enumerate(lines):
        if line == "Flights" and idx + 1 < len(lines):
            candidate = lines[idx + 1].strip().lower()
            if candidate in {"one way", "round trip"}:
                return candidate
    return ""


def _ready_for_search(details: FlightDetails, attempts: list[FieldAttempt]) -> bool:
    return not _unverified_required_fields(details, attempts)


def _unverified_required_fields(details: FlightDetails, attempts: list[FieldAttempt]) -> list[str]:
    by_field = {attempt.field: attempt for attempt in attempts}
    required = ["destination", "departure"]
    if details.return_date:
        required.append("return")
    missing = []
    for field in required:
        attempt = by_field.get(field)
        if not attempt or attempt.status not in {"verified", "already set"}:
            missing.append(field)
    return missing


def _workflow_value(details: FlightDetails) -> str:
    return f"flights:origin={details.origin};destination={details.destination};depart={details.depart};return={details.return_date};one_way={details.one_way}"


def _opened_reply(details: FlightDetails) -> str:
    lines = [
        "Flight search skill opened Google Flights with the stable URL only.",
        f"origin: {details.origin}",
        f"destination: {details.destination}",
        f"depart: {details.depart or 'unknown'}",
        f"return: {details.return_date or 'one way'}",
    ]
    if details.assumptions:
        lines.append("assumptions:")
        lines.extend(f"{idx}) {item}" for idx, item in enumerate(details.assumptions, 1))
    return "\n".join(lines)


def _clarification_reply(details: FlightDetails) -> str:
    questions = []
    if "departure date" in details.missing:
        questions.append("What departure date should I use?")
    if "destination" in details.missing:
        questions.append("Where are you flying to?")
    if "origin" in details.missing:
        questions.append("Where are you flying from?")
    lines = [
        "Flight search needs one detail before I open Google Flights.",
        f"origin: {details.origin}",
        f"destination: {details.destination or 'unknown'}",
        f"trip type: {'one way' if details.one_way else 'return'}",
        "I will assume one way unless you give me a return date.",
        " ".join(questions[:3]),
    ]
    if details.assumptions:
        lines.append("assumptions:")
        lines.extend(f"{idx}) {item}" for idx, item in enumerate(details.assumptions, 1))
    if details.missing:
        lines.append("missing: " + ", ".join(details.missing))
    return "\n".join(line for line in lines if line)


def extract_flight_options(text: str, destination: str, depart: str = "", limit: int = 5) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    options = []
    price_re = re.compile(r"\b(?:MYR|RM)\s*[\d,]+", re.I)
    date_tokens = _date_match_tokens(depart)
    for idx, line in enumerate(lines):
        if not price_re.search(line):
            continue
        window = lines[max(0, idx - 4): min(len(lines), idx + 5)]
        joined = " | ".join(window)
        if destination and destination.lower() not in joined.lower():
            continue
        if date_tokens and not any(token in joined.lower() for token in date_tokens):
            continue
        if joined not in options:
            options.append(joined)
        if len(options) >= limit:
            break
    if options:
        return options
    if date_tokens:
        return []
    for idx, line in enumerate(lines):
        if not price_re.search(line):
            continue
        window = lines[max(0, idx - 3): min(len(lines), idx + 4)]
        joined = " | ".join(window)
        if joined not in options:
            options.append(joined)
        if len(options) >= limit:
            break
    return options


def extract_date_grid_price(text: str, depart: str) -> str:
    parts = depart.split()
    if len(parts) < 2 or not parts[1].isdigit():
        return ""
    month = parts[0].lower()
    day = str(int(parts[1]))
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    month_idx = next((idx for idx, line in enumerate(lines) if line.lower() == month or line.lower().startswith(month[:3])), -1)
    if month_idx == -1:
        return ""
    month_names = {m.lower() for m in MONTHS if len(m) > 3}
    for idx in range(month_idx + 1, min(len(lines), month_idx + 140)):
        line = lines[idx]
        if idx > month_idx + 5 and line.lower() in month_names:
            break
        match = re.fullmatch(rf"{re.escape(day)}\s+(\d{{2,5}})", line)
        if match:
            return f"Date grid for {parts[0].title()} {day}: MYR {match.group(1)} shown by Google Flights; exact airline schedule was not opened yet."
        if line == day and idx + 1 < len(lines) and re.fullmatch(r"\d{2,5}", lines[idx + 1]):
            return f"Date grid for {parts[0].title()} {day}: MYR {lines[idx + 1]} shown by Google Flights; exact airline schedule was not opened yet."
    return ""


def _date_match_tokens(depart: str) -> list[str]:
    parts = depart.split()
    if len(parts) < 2 or not parts[1].isdigit():
        return []
    month = parts[0][:3].lower()
    day = str(int(parts[1]))
    return [f"{month} {day}", f"{parts[0].lower()} {day}"]


def _filled_reply(details: FlightDetails, attempts: list[FieldAttempt], price_options: list[str] | None = None, result_page: str = "") -> str:
    verified = [attempt for attempt in attempts if attempt.status in {"verified", "already set"}]
    failed = [attempt for attempt in attempts if attempt.status not in {"verified", "already set", "skipped"}]
    status = "ready for review" if len(verified) >= 2 and not failed else "needs manual check"
    if details.missing:
        status = "needs clarification"
    lines = [
        "Flight search skill used. Opened Google Flights with the stable URL only.",
        f"status: {status}",
        f"origin: {details.origin}",
        f"destination: {details.destination}",
        f"depart: {details.depart or 'unknown'}",
        f"return: {details.return_date or 'one way'}",
        "field results:",
    ]
    lines.extend(attempt.line() for attempt in attempts)
    if result_page:
        lines.append(f"result page: {result_page}")
    if price_options:
        lines.append("visible price options:")
        lines.extend(f"{idx}) {item}" for idx, item in enumerate(price_options, 1))
    else:
        lines.append("visible price options: none extracted from page text; use screenshot fallback if prices are visibly shown.")
    if details.assumptions:
        lines.append("assumptions:")
        lines.extend(f"{idx}) {item}" for idx, item in enumerate(details.assumptions, 1))
    if details.missing:
        lines.append("missing: " + ", ".join(details.missing))
    return "\n".join(lines)


MONTHS = {
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
    "jan",
    "feb",
    "mar",
    "apr",
    "jun",
    "jul",
    "aug",
    "sep",
    "sept",
    "oct",
    "nov",
    "dec",
}


KNOWN_DESTINATIONS = (
    "Penang",
    "Langkawi",
    "Kota Kinabalu",
    "Kuching",
    "Johor Bahru",
    "Kuala Terengganu",
    "Kuantan",
    "Ipoh",
    "Malacca",
    "Melaka",
    "Singapore",
    "Bangkok",
    "Tokyo",
    "Osaka",
    "Kyoto",
    "Seoul",
    "Taipei",
    "Hong Kong",
)
