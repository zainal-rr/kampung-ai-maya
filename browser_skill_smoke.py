from __future__ import annotations

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

        reply = await run_browser_skill(db_path, "find google images of modern kampung house", bridge=bridge)
        _require("Google Images" in reply, "image search reply missing")
        _require(bridge.urls[-1] == "https://www.google.com/search?tbm=isch&q=modern+kampung+house", "wrong image search URL")

        reply = await run_browser_skill(db_path, "search for best lightweight drone", bridge=bridge)
        _require("Google search" in reply, "web search reply missing")
        _require("best+lightweight+drone" in bridge.urls[-1], "wrong web search URL")

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
