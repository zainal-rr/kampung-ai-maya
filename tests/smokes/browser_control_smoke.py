from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import tempfile
from pathlib import Path

from maya_browser.browser_control import BrowserClickResult, BrowserController, element_summary, page_summary
from maya_browser.browser_workflows import HumanBrowserWorkflowRouter
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


class FakeFallbackBrowser:
    def __init__(self):
        self.search_clicks: list[str] = []

    def click_text_verified(self, target: str) -> BrowserClickResult:
        return BrowserClickResult(
            status="not_found",
            target=target,
            clicked_label="",
            before_title="Search",
            before_url="https://www.google.com/search?q=opr",
            after_title="Search",
            after_url="https://www.google.com/search?q=opr",
            before_hash="a",
            after_hash="a",
            before_modal="",
            after_modal="",
            target_present_after=False,
        )

    def click_search_result(self, target: str, rank: int = 1) -> str:
        self.search_clicks.append(target)
        if target.lower().endswith("search result"):
            return "NOT_FOUND"
        return f"CLICKED: rank={rank} {target}"


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
        _require("verified the browser" in reply.lower(), "workflow did not verify browser start")
        inspect = await router.handle("compare visible results", "telegram")
        _require("I inspected Chrome" in inspect, "browser workflow did not inspect DOM")
        _require("Clickable or fillable targets" in inspect, "browser workflow missed elements")
        _require("Screen view is available" in inspect, "browser workflow missed screen grounding")
        fake_fallback = FakeFallbackBrowser()
        router._browser = fake_fallback
        clicked = await router._click_target("OPR Decisions Bank Negara Malaysia search result", sensitive=False)
        _require("matching search result" in clicked, "search-result click fallback did not fire")
        _require(
            fake_fallback.search_clicks == [
                "OPR Decisions Bank Negara Malaysia search result",
                "OPR Decisions Bank Negara Malaysia",
            ],
            f"unexpected fallback candidates: {fake_fallback.search_clicks}",
        )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
