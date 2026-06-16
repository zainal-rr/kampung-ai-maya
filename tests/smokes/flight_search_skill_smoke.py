from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import json
import re
import tempfile
from pathlib import Path

from flight_search_skill import FlightSearchSkill
from storage import init_db


class FakeBridge:
    def __init__(self, *, search_available: bool):
        self.search_available = search_available
        self.opened_urls: list[str] = []
        self.clicks: list[str] = []
        self.typed: list[str] = []

    def get_frontmost_app(self) -> str:
        return "Google Chrome"

    def open_url_new_tab(self, url: str, app_name: str = "Google Chrome") -> None:
        self.opened_urls.append(url)

    def press_shortcut(self, shortcut: str) -> None:
        pass

    def type_text(self, text: str) -> None:
        self.typed.append(text)

    def _run_applescript(self, script: str) -> str:
        if "rawJson" in script:
            labels = [
                "One way",
                "Federal Territory of Kuala Lumpur",
                "Penang",
                "Sun, Jun 7",
                "Search",
            ]
            inputs = {"Federal Territory of Kuala Lumpur", "Penang", "Sun, Jun 7"}
            return json.dumps([{"kind": "input" if label in inputs else "button", "label": label} for label in labels])
        if "clickResult" in script:
            target = _target_from_script(script)
            self.clicks.append(target)
            if target == "explore":
                raise AssertionError("flight search must not click Explore as Search fallback")
            if target == "search" and not self.search_available:
                return "NOT_FOUND"
            return f"CLICKED: {target or 'field'}"
        if "fillResult" in script:
            target = _target_from_script(script)
            return f"FILLED: {target or 'field'}"
        if "---URL---" in script:
            return "Google Flights\n---URL---\nhttps://www.google.com/travel/flights\n---TEXT---\nOne way\nKuala Lumpur\nPenang\nSun, Jun 7\n"
        return json.dumps({
            "title": "Google Flights",
            "url": "https://www.google.com/travel/flights",
            "selection": "",
            "anchor": "",
            "nearby": "",
            "headings": "",
            "page": "Google Flights",
            "hidden": "",
        })


def _target_from_script(script: str) -> str:
    lowered = script.lower()
    match = re.search(r"const target\s*=\s*\"([^\"]+)\"", lowered)
    if match:
        return match.group(1)
    match = re.search(r"const target\s*=\s*\\\"([^\\\"]+)\\\"", lowered)
    if match:
        return match.group(1)
    if '\\"search\\"' in lowered or '"search"' in lowered:
        return "search"
    if '\\"explore\\"' in lowered or '"explore"' in lowered:
        return "explore"
    for target in ("search", "explore", "penang", "kuala lumpur", "where to?", "departure", "federal territory of kuala lumpur"):
        if json.dumps(target) in lowered:
            return target
    return ""


async def main() -> None:
    FlightSearchSkill.RESULT_WAIT_TIMEOUT = 0.6  # fake pages never show live result markers
    with tempfile.TemporaryDirectory(prefix="maya-flight-skill-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)

        no_search = FakeBridge(search_available=False)
        reply = await FlightSearchSkill(db_path, no_search).run("find flight from Kuala Lumpur to Penang on June 7")
        _require(no_search.opened_urls == ["https://www.google.com/travel/flights"], "did not open stable Google Flights URL")
        _require("explore" not in no_search.clicks, f"Explore fallback was clicked: {no_search.clicks}")
        _require("Search button not found" in reply, f"missing Search-not-found diagnostic: {reply}")

        with_search = FakeBridge(search_available=True)
        reply = await FlightSearchSkill(db_path, with_search).run("find flight from Kuala Lumpur to Penang on June 7")
        _require("search" in with_search.clicks, f"Search was not clicked: {with_search.clicks}")
        _require("explore" not in with_search.clicks, f"Explore was clicked despite Search: {with_search.clicks}")
        _require("destination: Penang" in reply, "destination missing from reply")
    print("flight_search_skill_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
