from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import json
import tempfile
from pathlib import Path

from browser_task_step import BrowserTaskStepper
from storage import init_db


class FakeBridge:
    def __init__(self):
        self.urls: list[str] = []

    def get_frontmost_app(self) -> str:
        return "Google Chrome"

    def open_url_new_tab(self, url: str, app_name: str = "Google Chrome") -> None:
        self.urls.append(url)

    def _run_applescript(self, script: str) -> str:
        if "rawJson" in script:
            return json.dumps([])
        return json.dumps({
            "title": "Kyoto and Osaka itinerary",
            "url": "https://example.test/itinerary",
            "selection": "",
            "anchor": "",
            "nearby": "Kyoto stay from August 30 2026 to September 4 2026",
            "headings": "Kyoto\nOsaka",
            "page": "Trip from Kuala Lumpur to Osaka with Kyoto stay from August 30 2026 to September 4 2026.",
            "hidden": "",
        })


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-stay-skill-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        bridge = FakeBridge()

        booking = await BrowserTaskStepper(db_path, bridge).step("find hotel in Kyoto on booking.com")
        _require("Booking.com skill used" in booking, "Booking.com skill was not used")
        _require("booking.com/searchresults.html?" in bridge.urls[-1], "Booking.com search URL was not opened")
        _require("ss=Kyoto" in bridge.urls[-1], "Booking.com location missing")
        _require("checkin=2026-08-30" in bridge.urls[-1], "Booking.com check-in missing")
        _require("checkout=2026-09-04" in bridge.urls[-1], "Booking.com checkout missing")
        _require("1 adult because guests were not specified" in booking, "Booking.com guest assumption missing")

        airbnb = await BrowserTaskStepper(db_path, bridge).step("find Airbnb in Osaka on August 30 2026")
        _require("Airbnb skill used" in airbnb, "Airbnb skill was not used")
        _require("airbnb.com/s/Osaka/homes?" in bridge.urls[-1], "Airbnb search URL was not opened")
        _require("checkin=2026-08-30" in bridge.urls[-1], "Airbnb check-in missing")
        _require("checkout=2026-08-31" in bridge.urls[-1], "Airbnb one-night checkout missing")
        _require("one night stay because only one date was provided" in airbnb, "Airbnb one-date assumption missing")

    print("stay_booking_skill_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
