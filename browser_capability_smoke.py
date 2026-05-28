from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from browser_capability import browser_child_skill_catalog, route_browser_capability, run_browser_capability
from storage import init_db


class FakeBridge:
    def __init__(self):
        self.urls: list[str] = []
        self.typed: list[str] = []

    def get_frontmost_app(self) -> str:
        return "Google Chrome"

    def open_url_new_tab(self, url: str, app_name: str = "Google Chrome") -> None:
        self.urls.append(url)

    def open_url(self, url: str, app_name: str = "Google Chrome") -> None:
        self.urls.append(url)

    def press_shortcut(self, shortcut: str) -> None:
        pass

    def type_text(self, text: str) -> None:
        self.typed.append(text)

    def _run_applescript(self, script: str) -> str:
        if "rawJson" in script:
            labels = ["One way", "Federal Territory of Kuala Lumpur", "Where to?", "Penang", "Sun, Jun 7", "Search"]
            return json.dumps([{"kind": "input", "label": label} for label in labels])
        if "clickResult" in script:
            return "CLICKED: Search"
        if "pageTitle" in script:
            return "Browser Page\n---URL---\nhttps://example.test\n---TEXT---\nPenang RM250\nGuest favourite RM420"
        return json.dumps({
            "title": "Current Itinerary",
            "url": "https://example.test/itinerary",
            "selection": "",
            "anchor": "",
            "nearby": "Trip to Penang on June 7 2026",
            "headings": "Penang",
            "page": "Trip to Penang on June 7 2026",
            "hidden": "",
        })


async def main() -> None:
    _require(route_browser_capability("find flight to Penang June 7").child_skill == "flight_search", "flight route failed")
    _require(route_browser_capability("find Airbnb in Penang").child_skill == "airbnb_stay_search", "airbnb route failed")
    _require(route_browser_capability("find hotel in Penang").child_skill == "booking_com_hotel_search", "hotel route failed")
    _require(route_browser_capability("google images modern kampung house").child_skill == "google_images", "image route failed")
    _require(route_browser_capability("open Chrome").child_skill == "general_browser", "general route failed")
    catalog = browser_child_skill_catalog()
    _require({item["id"] for item in catalog} >= {"general_browser", "google_images", "flight_search", "booking_com_hotel_search", "airbnb_stay_search"}, "catalog missing child skills")

    with tempfile.TemporaryDirectory(prefix="maya-browser-capability-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        bridge = FakeBridge()

        reply = await run_browser_capability(db_path, "google images modern kampung house", bridge=bridge)
        _require("Google Images" in reply, "google images did not run")
        _require("tbm=isch" in bridge.urls[-1], "google images URL missing image mode")

        reply = await run_browser_capability(db_path, "find flight to Penang June 7 2026", bridge=bridge)
        _require("Flight search skill used" in reply, "flight child skill did not run")
        _require(bridge.urls[-1] == "https://www.google.com/travel/flights", "flight child did not open stable URL")

    print("browser_capability_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
