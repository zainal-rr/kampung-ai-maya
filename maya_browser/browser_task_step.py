from __future__ import annotations

import asyncio
import re
from urllib.parse import urlsplit

from active_context import ActiveContextInspector
from browser_capability import run_browser_capability, route_browser_capability
from browser_driver import make_browser_controller
from browser_control import element_summary, page_summary
from browser_site_skill_helpers import _rank_from_text
from flight_search_reply import extract_flight_options
from stay_booking_parsing import extract_stay_options
from travel_booking_safety import travel_booking_boundary_reply, travel_booking_safety_footer
from travel_budget import save_travel_plan_fields
from utils import OSBridge


class BrowserTaskStepper:
    DETAIL_WAIT_SECONDS = 8.0

    def __init__(self, db_path: str, bridge: OSBridge | None = None):
        self.db_path = db_path
        self.bridge = bridge or OSBridge()
        self.browser = make_browser_controller(bridge)
        self.inspector = ActiveContextInspector(db_path, self.bridge)

    async def step(self, question: str) -> str:
        lowered = question.lower()
        sensitive_terms = ("pay", "passport", "card", "otp", "login", "submit")
        book_action = bool(re.search(r"\b(book|reserve)\b", lowered)) and "booking.com" not in lowered
        if book_action or any(word in lowered for word in sensitive_terms):
            return travel_booking_boundary_reply(question) or (
                "I can prepare or compare, but I will stop before booking, payment, login, or private details."
            )
        if any(word in lowered for word in ("click", "select", "open")) and any(word in lowered for word in ("result", "option", "listing", "hotel", "airbnb", "flight", "osaka", "kyoto")):
            return await self._open_travel_selection(question)
        route = route_browser_capability(question)
        if route.child_skill != "general_browser" or _is_general_browser_request(lowered):
            return await run_browser_capability(self.db_path, question, bridge=self.bridge)
        if lowered.startswith(("inspect", "what", "compare", "summarize")):
            return await self._inspect()
        return await self._inspect()

    async def _inspect(self) -> str:
        page, elements = await asyncio.gather(
            asyncio.to_thread(self.browser.inspect_page),
            asyncio.to_thread(self.browser.inspect_elements),
        )
        return page_summary(page) + "\n" + element_summary(elements)

    async def _open_travel_selection(self, question: str) -> str:
        before = await asyncio.to_thread(self.browser.inspect_page, 8000)
        selected = await _remember_selected_option(self.db_path, question, before.url, before.text)
        target = selected.click_target or _selection_target(question)
        clicked = await asyncio.to_thread(self.browser.click_price_result, target)
        await asyncio.sleep(self.DETAIL_WAIT_SECONDS)
        after = await asyncio.to_thread(self.browser.inspect_page, 5000)
        saved_line = f"\n{selected.reply_line}" if selected.reply_line else ""
        if clicked == "NOT_FOUND":
            return (
                "I could not find a visible priced result to open. "
                "If prices are visible on screen, I should use screenshot fallback."
                + saved_line
            )
        if before.url == after.url and ("search results" in after.text.lower() or before.text_hash == after.text_hash):
            return (
                "I clicked a visible priced selection, but the page did not open a new detail view. "
                "The site may require a more precise UI click or screenshot-guided click.\n"
                f"clicked: {clicked}\n"
                f"url: {after.url}"
                + saved_line
            )
        if _sensitive_page(after.text, after.url):
            return (
                "I opened the selection, but I am stopping here because this looks like a booking, "
                f"login, payment, or private-details page.\nURL: {after.url}"
                + saved_line
            )
        return (
            "Opened the visible priced selection for review.\n"
            f"clicked: {clicked}\n"
            f"before: {before.title}\n"
            f"now: {after.title}\n"
            f"url: {after.url}\n"
            + page_summary(after, max_lines=10)
            + saved_line
            + "\n"
            + travel_booking_safety_footer(1)
        )


async def browser_task_step(db_path: str, question: str) -> str:
    return await BrowserTaskStepper(db_path).step(question)


def _selection_target(question: str) -> str:
    lowered = question.lower()
    if any(word in lowered for word in ("first", "top", "cheapest", "visible", "listing", "result", "option")):
        for candidate in ("osaka", "kyoto", "tokyo", "singapore", "bangkok"):
            if candidate in lowered:
                return candidate
        return ""
    for candidate in ("osaka", "kyoto", "tokyo", "singapore", "bangkok"):
        if candidate in lowered:
            return candidate
    return ""


class _SelectedTravelOption:
    def __init__(self, reply_line: str = "", click_target: str = ""):
        self.reply_line = reply_line
        self.click_target = click_target


async def _remember_selected_option(db_path: str, question: str, url: str, page_text: str) -> _SelectedTravelOption:
    provider = _selection_provider(url)
    if not provider:
        return _SelectedTravelOption()
    options = _travel_options(provider, page_text)
    if not options:
        return _SelectedTravelOption()
    option = _selected_option(question, options)
    if not option:
        return _SelectedTravelOption()
    price = _selected_price_myr(option)
    if price is None:
        return _SelectedTravelOption(click_target=_click_target_from_option(option))
    rank = options.index(option) + 1
    if provider == "Google Flights":
        await save_travel_plan_fields(
            db_path,
            selected_flight_price_myr=price,
            selected_flight_option=option,
            flight_preference=f"selected option {rank} from Google Flights",
        )
        return _SelectedTravelOption(
            f"Saved selected flight option {rank} to the travel budget: MYR {price}.",
            _click_target_from_option(option),
        )
    await save_travel_plan_fields(
        db_path,
        selected_stay_price_myr=price,
        selected_stay_provider=provider,
        selected_stay_option=option,
        accommodation_type=provider,
        stay_price_notes=f"{provider} option {rank}: MYR {price}",
    )
    return _SelectedTravelOption(
        f"Saved selected {provider} stay option {rank} to the travel budget: MYR {price}.",
        _click_target_from_option(option),
    )


def _selection_provider(url: str) -> str:
    lowered = (url or "").lower()
    if "google.com/travel/flights" in lowered:
        return "Google Flights"
    if "booking.com" in lowered:
        return "Booking.com"
    if "airbnb." in lowered:
        return "Airbnb"
    return ""


def _travel_options(provider: str, text: str) -> list[str]:
    if provider in {"Booking.com", "Airbnb"}:
        return extract_stay_options(text, limit=8)
    if provider == "Google Flights":
        return extract_flight_options(text, "", "", limit=8)
    return []


def _selected_option(question: str, options: list[str]) -> str:
    lowered = question.lower()
    if "cheapest" in lowered:
        priced = [(idx, _selected_price_myr(option)) for idx, option in enumerate(options)]
        priced = [(idx, price) for idx, price in priced if price is not None]
        if priced:
            idx, _ = min(priced, key=lambda item: item[1])
            return options[idx]
    rank = _selection_rank(question)
    if rank <= len(options):
        return options[rank - 1]
    return options[0]


def _selection_rank(question: str) -> int:
    match = re.search(r"\b(?:option|listing|result|hotel|stay|flight)\s*(\d{1,2})\b", question, re.I)
    if match:
        return max(1, min(20, int(match.group(1))))
    return _rank_from_text(question)


def _selected_price_myr(option: str) -> int | float | None:
    matches = re.findall(r"\b(?:MYR|RM)\s*([\d,]+(?:\.\d+)?)", option, re.I)
    if not matches:
        return None
    raw = matches[-1].replace(",", "")
    try:
        value = float(raw)
    except ValueError:
        return None
    if value <= 0:
        return None
    return int(value) if value.is_integer() else round(value, 2)


def _click_target_from_option(option: str) -> str:
    price = re.findall(r"\b(?:MYR|RM)\s*([\d,]+(?:\.\d+)?)", option, re.I)
    if price:
        return price[-1].replace(",", "")
    parts = [part.strip() for part in option.split("|") if len(part.strip()) >= 5]
    for part in reversed(parts):
        if not re.search(r"\b(?:MYR|RM|price|night|adult|bed|bath)\b", part, re.I):
            return part[:80]
    return parts[0][:80] if parts else ""


def _sensitive_page(text: str, url: str) -> bool:
    parsed = urlsplit(url)
    lowered = f"{parsed.netloc}{parsed.path}\n{text}".lower()
    markers = (
        "payment",
        "checkout",
        "passport",
        "card number",
        "credit card",
        "otp",
        "password",
        "passenger details",
        "enter your details",
        "your details",
        "complete booking",
        "confirm booking",
        "final step",
    )
    return any(marker in lowered for marker in markers)


def _is_general_browser_request(lowered: str) -> bool:
    if any(word in lowered for word in ("flight", "airbnb", "booking.com", "hotel", "hotels", "room", "rooms", "accommodation")):
        return False
    markers = (
        "open browser",
        "open chrome",
        "show browser",
        "show chrome",
        "google image",
        "google images",
        "image search",
        "search images",
        "find images",
        "search for",
        "google ",
        "look up",
        "find online",
        "check online",
        "inspect browser",
        "read browser",
        "what is on chrome",
        "what is in chrome",
        "summarize this page",
        "summarise this page",
        "click ",
        "choose ",
        "select ",
        "press ",
        "fill ",
        "enter ",
        "type ",
    )
    return any(marker in lowered for marker in markers)
