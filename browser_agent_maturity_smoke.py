from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from browser_cost_policy import escalation_decision, local_decision
from browser_control import BrowserController
from browser_workflows import HumanBrowserWorkflowRouter
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
    pro = escalation_decision(reason="double check tiny text", confidence=0.4, careful=True)
    _require(pro.lane == "gemini_pro" and pro.allowed, "Pro escalation rule failed")

    with tempfile.TemporaryDirectory(prefix="maya-browser-agent-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        router = HumanBrowserWorkflowRouter(db_path, bridge, FakeScreen())
        started = await router.handle("check flight to Penang tomorrow", "telegram")
        _require("flight options" in started.lower(), "flight browser state did not start")
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
