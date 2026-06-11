from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from openpyxl import load_workbook

from browser_task_step import BrowserTaskStepper
from storage import get_preference, init_db
from travel_budget import TRAVEL_PLAN_KEY, TravelParty
from travel_budget_workbook import _build_workbook


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


class FakeBookingSelectionBridge:
    def __init__(self):
        self.clicked_targets: list[str] = []
        self.after_click = False

    def get_frontmost_app(self) -> str:
        return "Google Chrome"

    def _run_applescript(self, script: str) -> str:
        if "clickResult" in script:
            self.after_click = True
            self.clicked_targets.append(script)
            return "CLICKED: Shangri-La Golden Sands, Penang"
        if self.after_click:
            return (
                "Shangri-La Golden Sands, Penang\n"
                "---URL---\n"
                "https://www.booking.com/hotel/my/shangri-la-golden-sands.html\n"
                "---TEXT---\n"
                "Shangri-La Golden Sands, Penang\n"
                "Very Good 8.4\n"
                "Superior Twin Room\n"
                "2 nights, 2 adults\n"
                "MYR 840\n"
            )
        return (
            "Booking.com: Hotels in Penang\n"
            "---URL---\n"
            "https://www.booking.com/searchresults.html?ss=Penang&selected_currency=MYR\n"
            "---TEXT---\n"
            "Penang: 1,902 properties found\n"
            "Swing & Pillows - Grand Inn George Town Penang\n"
            "Very Good\n"
            "8.2\n"
            "2 nights, 2 adults\n"
            "MYR 113\n"
            "Shangri-La Golden Sands, Penang\n"
            "Very Good\n"
            "8.4\n"
            "2 nights, 2 adults\n"
            "MYR 840\n"
            "DoubleTree Resort by Hilton Hotel Penang\n"
            "Very Good\n"
            "8.3\n"
            "2 nights, 2 adults\n"
            "MYR 542\n"
        )


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
        old_wait = BrowserTaskStepper.DETAIL_WAIT_SECONDS
        BrowserTaskStepper.DETAIL_WAIT_SECONDS = 0
        try:
            selection_bridge = FakeBookingSelectionBridge()
            reply = await BrowserTaskStepper(db_path, selection_bridge).step("open option 2")
        finally:
            BrowserTaskStepper.DETAIL_WAIT_SECONDS = old_wait
        _require("Saved selected Booking.com stay option 2" in reply, "selected stay was not acknowledged")
        raw_plan = await get_preference(db_path, TRAVEL_PLAN_KEY)
        _require(raw_plan is not None, "travel plan was not saved")
        plan = json.loads(raw_plan)
        _require(plan.get("selected_stay_provider") == "Booking.com", "selected stay provider missing")
        _require(plan.get("selected_stay_price_myr") == 840, "selected stay price missing")
        _require("Shangri-La Golden Sands" in plan.get("selected_stay_option", ""), "selected stay option text missing")
        workbook_path = Path(tmp) / "selected-stay-budget.xlsx"
        _build_workbook(workbook_path, plan, TravelParty(2, "smoke test"))
        sheet = load_workbook(workbook_path, data_only=False)["Travel Budget"]
        values = [cell.value for row in sheet.iter_rows() for cell in row if cell.value not in (None, "")]
        joined = "\n".join(str(value) for value in values)
        _require("Booking.com" in joined, "workbook missing selected stay provider")
        _require("MYR 840" in reply and "840" in joined, "workbook missing selected stay price")
    print("browser_task_step_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
