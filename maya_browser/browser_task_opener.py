from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass

from maya_core.active_context import ActiveContextInspector
from maya_core.active_context_models import ActiveContext
from maya_browser.browser_capability import route_browser_capability, run_browser_capability
from maya_browser.browser_driver import make_browser_controller
from maya_core.permission_policy import action_permission
from storage import upsert_preference
from utils import OSBridge


@dataclass(frozen=True)
class BrowserTaskResult:
    query: str
    target: str
    context_title: str


class BrowserTaskOpener:
    def __init__(self, db_path: str, bridge: OSBridge | None = None):
        self.db_path = db_path
        self.bridge = bridge or OSBridge()
        self.browser = make_browser_controller(bridge)
        self.inspector = ActiveContextInspector(db_path, self.bridge)

    async def open_for_task(self, question: str) -> str:
        if action_permission("travel_search" if _is_travel_booking(question) else "browse_web") != "allow":
            return "I need your confirmation before browsing for that."
        route = route_browser_capability(question)
        if _is_travel_booking(question) or route.child_skill not in {"general_browser"}:
            return await run_browser_capability(self.db_path, question, bridge=self.bridge)
        context = await self.inspector.inspect(question, allow_screen_fallback=False)
        result = _build_result(question, context)
        await asyncio.to_thread(self.browser.open_search_new_tab, result.query)
        await upsert_preference(self.db_path, "maya_active_workflow", f"{result.target}:{result.query}", source="workflow")
        title = f" using {result.context_title}" if result.context_title else ""
        return f"I opened a new Chrome tab for that search{title}."


async def open_browser_for_task(db_path: str, question: str) -> str:
    return await BrowserTaskOpener(db_path).open_for_task(question)


def _build_result(question: str, context: ActiveContext) -> BrowserTaskResult:
    target = "flights" if _is_flight(question) else "search"
    query = _query_from_context(question, context, target)
    return BrowserTaskResult(query=query, target=target, context_title=context.active_title)


def _query_from_context(question: str, context: ActiveContext, target: str) -> str:
    base = _clean_question(question)
    context_text = " ".join(
        part for part in (
            context.active_title,
            context.selected_content,
            context.nearby_context,
            context.document_context,
        )
        if part
    )
    context_text = _compact(context_text)
    if target == "flights":
        if _is_vague_trip_request(base) and context_text:
            return _clip_query(f"flights for trip {context_text}")
        return _clip_query(f"{base} {context_text}" if context_text else base)
    return _clip_query(f"{base} {context_text}" if context_text else base)


def _is_flight(text: str) -> bool:
    lowered = text.lower()
    return "flight" in lowered or "flights" in lowered


def _is_airbnb(text: str) -> bool:
    lowered = text.lower()
    return "airbnb" in lowered


def _is_hotel(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in ("booking.com", "hotel", "hotels", "room", "rooms", "accommodation"))


def _is_travel_booking(text: str) -> bool:
    return _is_flight(text) or _is_airbnb(text) or _is_hotel(text)


def _is_vague_trip_request(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in ("this trip", "my trip", "the trip", "this itinerary", "this day"))


def _clean_question(text: str) -> str:
    cleaned = " ".join(text.strip().split())
    cleaned = re.sub(r"\b(can you|please|for me|maya)\b", " ", cleaned, flags=re.I)
    return " ".join(cleaned.split()) or "search"


def _compact(text: str) -> str:
    lines = [line.strip() for line in re.split(r"[\n\r]+", text) if line.strip()]
    useful = [line for line in lines if not line.lower().startswith(("limits:", "context_source:", "confidence:"))]
    return " ".join(useful[:18])


def _clip_query(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text[:260].rstrip()
