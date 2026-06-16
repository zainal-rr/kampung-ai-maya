from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


"""Extension browser proof: explicit travel requests must not inspect active context.

W6 requires normal browser automation to stay on the Chrome extension path.
Flight/stay skills may still inspect active context for "this trip" style
requests, but explicit requests already contain their fields and must not call
AppleScript-backed active context first.
"""

import asyncio
import tempfile
from pathlib import Path

from maya_browser.browser_control import BrowserPage
from maya_browser.browser_control_js import _text_hash
from flight_search_skill import FlightSearchSkill
from flight_search_skill_smoke import FakeBridge
from flight_deeplink_smoke import RESULTS_PAGE
from stay_booking_skill import BookingComHotelSkill
from storage import init_db


class RaisingInspector:
    async def inspect(self, *args, **kwargs):
        raise AssertionError("explicit extension request should not inspect active context")


class FakeFlightExtension:
    DRIVER = "extension"

    def __init__(self):
        self.opened: list[str] = []

    def open_new_tab_url(self, url: str) -> int:
        self.opened.append(url)
        return 1

    def inspect_page(self, max_chars: int = 4500) -> BrowserPage:
        text = RESULTS_PAGE[:max_chars]
        return BrowserPage("KUL to PEN | Google Flights", "https://www.google.com/travel/flights?q=test", text, _text_hash(text))


class FakeStayExtension:
    DRIVER = "extension"

    def __init__(self):
        self.opened: list[str] = []

    def open_new_tab_url(self, url: str) -> int:
        self.opened.append(url)
        return 2

    def inspect_page(self, max_chars: int = 4500) -> BrowserPage:
        text = (
            "Booking.com\nPenang: 1,902 properties found\n"
            "Shangri-La Golden Sands, Penang\nVery Good 8.4\n2 nights, 2 adults\nMYR 840\n"
            "DoubleTree Resort by Hilton Hotel Penang\nVery Good 8.3\nMYR 542\n"
        )
        return BrowserPage("Booking.com: Hotels in Penang", "https://www.booking.com/searchresults.html?ss=Penang", text, _text_hash(text))


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-extension-context-skip-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)

        flight = FlightSearchSkill(db_path, FakeBridge(search_available=True))
        flight.browser = FakeFlightExtension()
        flight.inspector = RaisingInspector()
        reply = await flight.run("find flights to Penang on June 24")
        _require("ready for review" in reply, "flight extension request did not complete")
        _require(flight.browser.opened, "flight extension did not open a deep link")

        stay = BookingComHotelSkill(db_path, FakeBridge(search_available=True))
        stay.browser = FakeStayExtension()
        stay.inspector = RaisingInspector()
        reply = await stay.run("find hotels in Penang on Booking.com from June 24 to June 26 for 2 adults")
        _require("Booking.com" in reply and "MYR" in reply, "stay extension request did not complete")
        _require(stay.browser.opened, "stay extension did not open a URL")

    print("browser_extension_context_skip_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
