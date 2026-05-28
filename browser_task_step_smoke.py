from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from browser_task_step import BrowserTaskStepper
from storage import init_db


class FakeBridge:
    def __init__(self):
        self.urls: list[str] = []
        self.typed: list[str] = []

    def get_frontmost_app(self) -> str:
        return "Google Chrome"

    def open_url_new_tab(self, url: str, app_name: str = "Google Chrome") -> None:
        self.urls.append(url)

    def _run_applescript(self, script: str) -> str:
        if "rawJson" in script:
            labels = ["Federal Territory of Kuala Lumpur", "Where to?", "Osaka", "Sun, Aug 30", "Fri, Sep 4"]
            return json.dumps([{"kind": "input", "label": label} for label in labels])
        if "clickResult" in script:
            return "CLICKED: field"
        return json.dumps({
            "title": "Trip to Kyoto and Osaka",
            "url": "https://example.test/itinerary",
            "selection": "",
            "anchor": "",
            "nearby": "Trip runs August 30 2026 to September 4 2026",
            "headings": "Kyoto\nOsaka",
            "page": "Kuala Lumpur to Osaka itinerary from August 30 2026 until September 4 2026",
            "hidden": "",
        })

    def press_shortcut(self, shortcut: str) -> None:
        pass

    def type_text(self, text: str) -> None:
        self.typed.append(text)


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-browser-step-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        bridge = FakeBridge()
        reply = await BrowserTaskStepper(db_path, bridge).step("find flights for this trip")
        _require(bridge.urls == ["https://www.google.com/travel/flights"], "did not open short Google Flights URL")
        _require("?q=" not in bridge.urls[0], "flight task leaked context into q URL")
        _require("August 30 2026" in reply, "departure date missing")
        _require("September 4 2026" in reply, "return date missing")
        _require("destination: already set Osaka" in reply or "destination: verified Osaka" in reply, "destination not verified")
    print("browser_task_step_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
