from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from browser_control import BrowserController, element_summary, page_summary
from browser_workflows import HumanBrowserWorkflowRouter
from screen_service import ScreenSnapshot
from storage import init_db


class FakeBridge:
    def __init__(self):
        self.scripts: list[str] = []

    def _run_applescript(self, script: str) -> str:
        self.scripts.append(script)
        if "pageTitle" in script:
            return "Flights\n---URL---\nhttps://example.test\n---TEXT---\nAirAsia RM120\nMalaysia Airlines RM180"
        if "rawJson" in script:
            return '[{"kind":"button","label":"AirAsia"},{"kind":"input","label":"Depart date"}]'
        if "fillResult" in script:
            return "FILLED: depart date"
        return "CLICKED: AirAsia"

    def open_url(self, url: str, app_name: str = "Google Chrome") -> None:
        self.url = url

    def open_url_new_tab(self, url: str, app_name: str = "Google Chrome") -> None:
        self.new_tab_url = url


class FakeScreen:
    def capture_once(self):
        return ScreenSnapshot(True, "screen visible", b"fake-png")


def main() -> None:
    bridge = FakeBridge()
    browser = BrowserController(bridge)
    browser.open_search("flight to Penang")
    _require("flight+to+Penang" in bridge.url, "search URL was not encoded")
    browser.open_search_new_tab("flight to Kyoto")
    _require("flight+to+Kyoto" in bridge.new_tab_url, "new tab search URL was not encoded")

    page = browser.inspect_page()
    _require(page.title == "Flights", "title parse failed")
    _require("AirAsia" in page_summary(page), "page summary missed visible text")
    elements = browser.inspect_elements()
    _require("Depart date" in element_summary(elements), "element summary missed input")
    _require(browser.fill_field("depart date", "tomorrow") == "FILLED: depart date", "field fill failed")

    clicked = browser.click_text("AirAsia")
    _require(clicked == "CLICKED: AirAsia", "click result failed")
    verified = browser.click_text_verified("AirAsia")
    _require(verified.clicked and not verified.changed, "verified click result failed")
    asyncio.run(_workflow_grounding())
    print("browser_control_smoke: ok")


async def _workflow_grounding() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-browser-grounding-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        bridge = FakeBridge()
        router = HumanBrowserWorkflowRouter(db_path, bridge, FakeScreen())
        reply = await router.handle("browse flight to Penang", "imac")
        _require("opened chrome" in reply.lower(), "workflow did not start")
        inspect = await router.handle("compare visible results", "telegram")
        _require("I inspected Chrome" in inspect, "browser workflow did not inspect DOM")
        _require("Clickable or fillable targets" in inspect, "browser workflow missed elements")
        _require("Screen view is available" in inspect, "browser workflow missed screen grounding")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
