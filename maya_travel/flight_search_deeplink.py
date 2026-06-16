from __future__ import annotations

"""Direct-to-results Google Flights navigation for the extension driver.

The AppleScript driver fills the flight form with keyboard autocomplete, which
the Chrome extension cannot simulate. Instead the extension driver navigates
the validated deep link (`/travel/flights?q=one way flights from X to Y on
ISO-DATE`), which lands directly on a results page, then extracts options with
the same grounded extractors as the form path.
"""

import asyncio
from datetime import datetime
from urllib.parse import quote_plus

from maya_browser.browser_control import note_browser_intent
from maya_browser.browser_observe import wait_for_content
from maya_browser.browser_understanding import extract_browser_options_with_gemini, grounded_browser_options
from flight_search_form_helpers import capture_result_page
from flight_search_models import FieldAttempt, FlightDetails
from flight_search_reply import (
    _filled_reply,
    _workflow_value,
    extract_date_grid_price,
    extract_flight_options,
)
from storage import upsert_preference


def is_extension_driver(browser) -> bool:
    return getattr(browser, "DRIVER", "applescript") == "extension"


def note_flight_intent(details: FlightDetails) -> None:
    note_browser_intent(
        {
            "origin": details.origin,
            "destination": details.destination,
            "depart": details.depart,
            "return": details.return_date or "one way",
            "trip_type": "one way" if details.one_way else "return",
            "missing": ", ".join(details.missing),
        }
    )


def flights_deep_link(details: FlightDetails) -> str:
    parts = [
        "round trip" if details.return_date else "one way",
        "flights from",
        details.origin,
        "to",
        details.destination,
        "on",
        _iso(details.depart),
    ]
    if details.return_date:
        parts.extend(["returning", _iso(details.return_date)])
    return "https://www.google.com/travel/flights?q=" + quote_plus(" ".join(parts))


async def run_flight_deep_link(skill, details: FlightDetails) -> str:
    url = flights_deep_link(details)
    await asyncio.to_thread(skill.browser.open_new_tab_url, url)
    readiness = await asyncio.to_thread(
        wait_for_content,
        skill.browser,
        min_chars=1200,
        require_any=skill.RESULT_MARKERS,
        timeout_seconds=skill.RESULT_WAIT_TIMEOUT,
        stable_seconds=1.0,
        max_chars=14000,
    )
    page = readiness.page if readiness.page.url else await asyncio.to_thread(skill.browser.inspect_page, 14000)
    capture_result_page(skill, page)
    options = extract_flight_options(page.text, details.destination, details.depart)
    if not options:
        grid = extract_date_grid_price(page.text, details.depart)
        options = [grid] if grid else []
    if not options and page.text:
        gemini = await extract_browser_options_with_gemini(
            skill.db_path,
            provider="Google Flights",
            goal=f"{details.origin} to {details.destination} on {details.depart}",
            page_title=page.title,
            page_url=page.url,
            page_text=page.text,
        )
        options = grounded_browser_options(gemini, page.text)
    skill.last_price_options = options
    attempts = [
        FieldAttempt("deep link", url, "verified", "extension driver: navigated straight to results"),
        FieldAttempt("results", "Search", "verified" if options else "not verified", readiness.reason),
    ]
    await upsert_preference(skill.db_path, "maya_active_workflow", _workflow_value(details), source="skill")
    return _filled_reply(details, attempts, options, skill.last_result_page)


def _iso(date_text: str) -> str:
    for pattern in ("%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(date_text, pattern).date().isoformat()
        except ValueError:
            continue
    return date_text
