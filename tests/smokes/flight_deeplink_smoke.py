from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


"""Offline proof of the extension-driver flight deep link.

Checks the deep-link builder (one-way and return formats), and runs the full
FlightSearchSkill path with a fake extension-driver controller: the skill must
navigate the deep link directly (no form filling), wait for results, extract
real flight rows, and report honestly.
"""

import asyncio
import tempfile
from pathlib import Path

from maya_browser.browser_control import BrowserPage
from maya_browser.browser_control_js import _text_hash
from maya_travel.flight_search_deeplink import flights_deep_link
from maya_travel.flight_search_models import FlightDetails
from maya_travel.flight_search_skill import FlightSearchSkill
from flight_search_skill_smoke import FakeBridge
from maya_core.storage import init_db


RESULTS_PAGE = (
    "Flight search\nOne way\n1\nEconomy\nFederal Territory of Kuala Lumpur\nGeorge Town\n"
    "Search results\n30 results returned.\nBest\nCheapest\nfrom MYR 134\nSorted by top flights\n"
    "12:25 PM\n -\n1:25 PM\nBatik Air\n1 hr\nKUL–PEN\nNonstop\nMYR 151\n"
    "10:40 AM\n -\n11:35 AM\nAirAsia\n55 min\nKUL–PEN\nNonstop\nMYR 158\n"
    "11:50 AM\n -\n12:50 PM\nAirAsia X\n1 hr\nKUL–PEN\nNonstop\nMYR 158\n"
) + "Self-transfer and partner itineraries may be shown when cheaper. Prices include required taxes and fees.\n" * 8


class FakeExtensionController:
    DRIVER = "extension"

    def __init__(self):
        self.opened: list[str] = []

    def open_new_tab_url(self, url: str) -> int:
        self.opened.append(url)
        return 42

    def inspect_page(self, max_chars: int = 4500) -> BrowserPage:
        text = RESULTS_PAGE[:max_chars]
        return BrowserPage("KUL to PEN | Google Flights", "https://www.google.com/travel/flights?q=test", text, _text_hash(text))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def _main() -> None:
    one_way = FlightDetails(origin="Kuala Lumpur", destination="Penang", depart="June 24 2026")
    url = flights_deep_link(one_way)
    _require("one+way+flights+from+Kuala+Lumpur+to+Penang+on+2026-06-24" in url, f"one-way deep link wrong: {url}")
    round_trip = FlightDetails(
        origin="Kuala Lumpur", destination="Singapore", depart="September 2 2026",
        return_date="September 6 2026", one_way=False,
    )
    url = flights_deep_link(round_trip)
    _require("round+trip" in url and "returning+2026-09-06" in url, f"return deep link wrong: {url}")

    with tempfile.TemporaryDirectory(prefix="maya-deeplink-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        skill = FlightSearchSkill(db_path, FakeBridge(search_available=True))
        skill.RESULT_WAIT_TIMEOUT = 6.0
        fake = FakeExtensionController()
        skill.browser = fake
        reply = await skill.run("find flights to Penang on June 24")
        _require(len(fake.opened) == 1 and "travel/flights?q=" in fake.opened[0], f"deep link not opened: {fake.opened}")
        _require("one+way+flights+from" in fake.opened[0], "deep link query missing")
        _require("deep link: verified" in reply, "deep link attempt not reported")
        _require("MYR 151" in reply or "MYR 158" in reply, f"flight options not extracted:\n{reply[:400]}")
        _require("ready for review" in reply, "deep link run should be ready for review")

    print("flight_deeplink_smoke: ok")


if __name__ == "__main__":
    asyncio.run(_main())
