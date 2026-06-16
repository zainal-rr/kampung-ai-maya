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

from maya_browser.browser_cost_policy import escalation_decision, local_decision
from maya_browser.browser_control import BrowserController
from maya_browser.browser_workflows import HumanBrowserWorkflowRouter
from screen_service import ScreenSnapshot
from storage import init_db


class FakeBridge:
    def __init__(self):
        self.url = ""
        self.clicked = False

    def open_url(self, url: str, app_name: str = "Google Chrome") -> None:
        self.url = url

    def _run_applescript(self, script: str) -> str:
        if "pageTitle" in script:
            text = "Option A RM120\nOption B RM180" if not self.clicked else "Option A selected\nContinue"
            return f"Flights\n---URL---\nhttps://example.test/flights\n---TEXT---\n{text}"
        if "rawJson" in script:
            return '[{"kind":"button","label":"Option A"},{"kind":"input","label":"Depart date"}]'
        if "visibleResult" in script:
            return "false" if self.clicked else "true"
        if "clickResult" in script:
            self.clicked = True
            return "CLICKED: Option A"
        if "fillResult" in script:
            return "FILLED: depart date"
        return ""


class FakeScreen:
    def capture_once(self):
        return ScreenSnapshot(True, "screen visible", b"fake-screen")


async def main() -> None:
    bridge = FakeBridge()
    controller = BrowserController(bridge)
    result = controller.click_text_verified("Option A")
    _require(result.verified, "dynamic DOM click was not verified")
    _require(result.changed, "text hash change was not detected")

    local = local_decision()
    _require(local.lane == "local" and local.estimated_cost == 0, "local path should be free")
    premium = escalation_decision(reason="double check tiny text", confidence=0.4, careful=True)
    _require(premium.lane == "gemini_premium" and premium.allowed, "premium escalation rule failed")

    with tempfile.TemporaryDirectory(prefix="maya-browser-agent-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        router = HumanBrowserWorkflowRouter(db_path, bridge, FakeScreen())
        started = await router.handle("check flight to Penang tomorrow", "imac")
        _require("verified the browser" in started.lower(), "flight browser state did not start")
        unrelated = await router.handle("how does that relate to the Word document test we did earlier?", "telegram")
        _require(unrelated is None, "unrelated chat follow-up should not become a browser filter")
        refined = await router.handle("make it cheaper", "telegram")
        _require("verified the updated browser search" in refined.lower(), "real browser filter follow-up should still work")
        inspected = await router.handle("compare visible results", "telegram")
        _require("Estimated" not in inspected, "inspect should not expose noisy internals")
        _require("Cost path: local browser evidence only." in inspected, "local cost path missing")
        status = await router.handle("what are you comparing", "telegram")
        _require("Task type: flight_search" in status, "browser state task type missing")
        _require("Current page: Flights" in status, "browser state page title missing")
        sensitive = await router.handle("click pay now", "telegram")
        _require("Say yes" in sensitive, "sensitive click did not pause")
    print("browser_agent_maturity_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
