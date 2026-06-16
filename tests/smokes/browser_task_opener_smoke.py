from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from browser_task_opener import BrowserTaskOpener
from storage import get_preference, init_db


class FakeBridge:
    def __init__(self):
        self.new_tab_url = ""
        self.opened_urls: list[str] = []
        self.typed: list[str] = []

    def get_frontmost_app(self) -> str:
        return "Google Chrome"

    def _run_applescript(self, script: str) -> str:
        if "rawJson" in script:
            labels = ["Federal Territory of Kuala Lumpur", "Where to?", "Osaka", "Sun, Aug 30"]
            return json.dumps([{"kind": "input", "label": label} for label in labels])
        if "clickResult" in script:
            return "CLICKED: field"
        return json.dumps({
            "title": "Kyoto 4 Day Itinerary",
            "url": "https://example.test/itinerary",
            "selection": "Day 2 Higashiyama traditional pottery shops",
            "anchor": "Day 2 Higashiyama traditional pottery shops and tea houses",
            "nearby": "Second Day in Kyoto. Higashiyama. Traditional pottery shops.",
            "headings": "Day 1\nDay 2\nDay 3",
            "page": "Kyoto itinerary with Day 2 in Higashiyama and Day 4 departure.",
            "hidden": "arrival KUL to KIX",
        })

    def open_url_new_tab(self, url: str, app_name: str = "Google Chrome") -> None:
        self.new_tab_url = url
        self.opened_urls.append(url)

    def press_shortcut(self, shortcut: str) -> None:
        pass

    def type_text(self, text: str) -> None:
        self.typed.append(text)


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-browser-task-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        bridge = FakeBridge()
        opener = BrowserTaskOpener(db_path, bridge)
        reply = await opener.open_for_task("can you find me flight for this trip")
        _require("Flight search needs one detail" in reply, "missing date should ask, not assume a hardcoded trip date")
        _require("destination: Osaka" in reply, "destination from the active 'this trip' itinerary context should be used")
        _require("What departure date should I use?" in reply, "missing date should ask a direct question")
        _require("August 30 2026" not in reply, "hardcoded Japan trip date must not come back")
        _require(not bridge.opened_urls, "flight search should not open the browser without a departure date")
        active = await get_preference(db_path, "maya_active_workflow")
        _require(active and active.startswith("flights:"), "flight workflow state missing")
        opened_before = list(bridge.opened_urls)
        penang = await opener.open_for_task("show me flight to penang")
        _require("destination: Penang" in penang, f"explicit lowercase destination was overridden by context: {penang}")
        _require("destination: Osaka" not in penang, f"stale context destination leaked into Penang request: {penang}")
        _require("missing: departure date" in penang, "explicit destination without date should ask for date instead of using Japan trip date")
        _require("What departure date should I use?" in penang, "missing date should ask a direct clarification")
        _require(bridge.opened_urls == opened_before, "flight search should not open Google Flights without a departure date")
        reply = await opener.open_for_task("open github")
        _require("Browser capability opened GitHub" in reply, "frequent site did not bypass generic browser search")
        _require(bridge.opened_urls[-1] == "https://github.com", "frequent site opened wrong URL from task opener")
    print("browser_task_opener_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
