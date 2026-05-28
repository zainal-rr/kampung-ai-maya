from __future__ import annotations

import asyncio
import re
from urllib.parse import urlsplit

from active_context import ActiveContextInspector
from browser_capability import run_browser_capability, route_browser_capability
from browser_control import BrowserController, element_summary, page_summary
from utils import OSBridge


class BrowserTaskStepper:
    def __init__(self, db_path: str, bridge: OSBridge | None = None):
        self.db_path = db_path
        self.bridge = bridge or OSBridge()
        self.browser = BrowserController(self.bridge)
        self.inspector = ActiveContextInspector(db_path, self.bridge)

    async def step(self, question: str) -> str:
        lowered = question.lower()
        sensitive_terms = ("pay", "passport", "card", "otp", "login", "submit")
        book_action = bool(re.search(r"\b(book|reserve)\b", lowered)) and "booking.com" not in lowered
        if book_action or any(word in lowered for word in sensitive_terms):
            return "I can prepare or compare, but I will stop before booking, payment, login, or private details."
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
        target = _selection_target(question)
        before = await asyncio.to_thread(self.browser.inspect_page, 1600)
        clicked = await asyncio.to_thread(self.browser.click_price_result, target)
        await asyncio.sleep(8.0)
        after = await asyncio.to_thread(self.browser.inspect_page, 5000)
        if clicked == "NOT_FOUND":
            return "I could not find a visible priced result to open. If prices are visible on screen, I should use screenshot fallback."
        if before.url == after.url and ("search results" in after.text.lower() or before.text_hash == after.text_hash):
            return (
                "I clicked a visible priced selection, but the page did not open a new detail view. "
                "The site may require a more precise UI click or screenshot-guided click.\n"
                f"clicked: {clicked}\n"
                f"url: {after.url}"
            )
        if _sensitive_page(after.text, after.url):
            return f"I opened the selection, but I am stopping here because this looks like a booking, login, payment, or private-details page.\nURL: {after.url}"
        return (
            "Opened the visible priced selection for review.\n"
            f"clicked: {clicked}\n"
            f"before: {before.title}\n"
            f"now: {after.title}\n"
            f"url: {after.url}\n"
            + page_summary(after, max_lines=10)
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
