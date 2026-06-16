from __future__ import annotations

import asyncio
import re
from urllib.parse import quote_plus

from maya_core.permission_policy import action_permission
from utils import OSBridge


FLIGHT_MARKERS = ("flight", "flights", "airline", "ticket", "airasia", "malaysia airlines")
TRAVEL_ACTIONS = ("book", "buy", "find", "search", "check", "compare", "price")


class WebActionRouter:
    def __init__(self, bridge: OSBridge | None = None):
        self.bridge = bridge or OSBridge()

    async def handle(self, text: str, channel: str) -> str | None:
        request = self._parse(text)
        if request is None:
            return None
        kind, query = request
        permission = action_permission("travel_search" if kind == "flight" else "browse_web")
        if permission != "allow":
            return "I need your confirmation before doing that."

        url = _search_url(query)
        try:
            await asyncio.to_thread(self.bridge.open_url, url)
        except Exception as exc:
            return f"I couldn't open the browser search right now: {exc}"
        if kind == "flight":
            return (
                "I opened a browser search for flight options. I can compare prices, dates, "
                "airlines, baggage, and timing, but I will not book or pay until you confirm the exact choice."
            )
        return "I opened a browser search for that."

    @staticmethod
    def _parse(text: str) -> tuple[str, str] | None:
        cleaned = " ".join(text.strip().split())
        lowered = cleaned.lower()
        if _is_flight_request(lowered):
            return "flight", cleaned

        match = re.match(
            r"^(?:search the web for|search online for|browse the internet for|google|look up online)\s+(.+)$",
            cleaned,
            re.IGNORECASE,
        )
        if match:
            return "web", match.group(1).strip()
        return None


def _is_flight_request(lowered: str) -> bool:
    has_flight = any(marker in lowered for marker in FLIGHT_MARKERS)
    has_action = any(action in lowered.split() for action in TRAVEL_ACTIONS)
    return has_flight and has_action


def _search_url(query: str) -> str:
    return "https://www.google.com/search?q=" + quote_plus(query)
