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

from browser_skill import parse_browser_intent, run_browser_skill
from browser_task_step import BrowserTaskStepper
from storage import init_db


class FakeBridge:
    def __init__(self):
        self.urls: list[str] = []

    def open_url_new_tab(self, url: str, app_name: str = "Google Chrome") -> None:
        self.urls.append(url)

    def open_url(self, url: str, app_name: str = "Google Chrome") -> None:
        self.urls.append(url)

    def _run_applescript(self, script: str) -> str:
        if "pageTitle" in script:
            return "Search Results\n---URL---\nhttps://www.google.com/search?q=test\n---TEXT---\nResult one\nResult two"
        if "rawJson" in script:
            return '[{"kind":"button","label":"Images"},{"kind":"input","label":"Search"}]'
        if "fillResult" in script:
            return "FILLED: search"
        if "clickResult" in script:
            return "CLICKED: Images"
        if "visibleResult" in script:
            return "false"
        return ""


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-browser-skill-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        bridge = FakeBridge()

        intent = parse_browser_intent("find google images of modern kampung house")
        _require(intent.action == "image_search", "image intent not detected")
        _require(intent.target == "modern kampung house", "image query not cleaned")

        intent = parse_browser_intent("open Google Images and search for modern kampung house")
        _require(intent.action == "image_search", "image phrase intent not detected")
        _require(intent.target == "modern kampung house", f"image command wrapper leaked into query: {intent.target}")

        intent = parse_browser_intent("open Google Images and search for Pokémon")
        _require(intent.target == "Pokémon", f"unicode image query was not preserved: {intent.target}")

        reply = await run_browser_skill(db_path, "Can you gind a Google image of nasi lemak", bridge=bridge)
        _require("Google Images" in reply, "misspelled image request should route to Google Images")
        _require("q=nasi+lemak" in bridge.urls[-1], f"misspelled image request used wrong URL: {bridge.urls[-1]}")

        reply = await run_browser_skill(db_path, "Can you Google say modern kampung house", bridge=bridge)
        _require("Google search" in reply, "misheard Google search request should route to search")
        _require("modern+kampung+house" in bridge.urls[-1], f"misheard Google search used wrong URL: {bridge.urls[-1]}")

        reply = await run_browser_skill(db_path, "find google images of modern kampung house", bridge=bridge)
        _require("Google Images" in reply, "image search reply missing")
        _require("udm=2" in bridge.urls[-1], "image search should use the current Google Images URL format")
        _require("visible image results" in reply, "image search must report extracted results or admit it cannot read them")
        _require(bridge.urls[-1] == "https://www.google.com/search?udm=2&q=modern+kampung+house", "wrong image search URL")

        reply = await run_browser_skill(db_path, "search for best lightweight drone", bridge=bridge)
        _require("Google search" in reply, "web search reply missing")
        _require("best+lightweight+drone" in bridge.urls[-1], "wrong web search URL")

        before = len(bridge.urls)
        reply = await run_browser_skill(db_path, "google search, uh, the", bridge=bridge)
        _require(reply == "What should I search for?", "incomplete filler search should ask for a topic")
        _require(len(bridge.urls) == before, "incomplete filler search must not open a literal Google URL")

        reply = await run_browser_skill(db_path, "open browser", bridge=bridge)
        _require(bridge.urls[-1] == "https://www.google.com", "open browser did not open Google home")

        reply = await BrowserTaskStepper(db_path, bridge).step("google images of rice terraces")
        _require("Google Images" in reply, "voice wrapper did not route to browser skill")
        _require(bridge.urls[-1].endswith("q=rice+terraces"), "voice wrapper image URL wrong")

        reply = await BrowserTaskStepper(db_path, bridge).step("open Google Images and search for modern kampung house")
        _require(bridge.urls[-1].endswith("q=modern+kampung+house"), f"command wrapper leaked into URL: {bridge.urls[-1]}")

        reply = await BrowserTaskStepper(db_path, bridge).step("inspect browser")
        _require("Browser skill inspected Chrome" in reply, "inspect did not use browser skill")

    print("browser_skill_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
