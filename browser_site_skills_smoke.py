from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from browser_capability import route_browser_capability, run_browser_capability
from browser_site_skill_helpers import _is_result_open_request, _target_from_click_request
from storage import init_db


class FakeBridge:
    def __init__(self):
        self.urls: list[str] = []

    def open_url_new_tab(self, url: str, app_name: str = "Google Chrome") -> None:
        self.urls.append(url)

    def open_url(self, url: str, app_name: str = "Google Chrome") -> None:
        self.urls.append(url)

    def _run_applescript(self, script: str) -> str:
        if "CLICKED_RESULT" in script:
            return "CLICKED_RESULT: Example Result | https://example.test/result"
        if "pageTitle" in script:
            url = self.urls[-1] if self.urls else "https://example.test"
            if "youtube.com" in url:
                return "YouTube Search\n---URL---\n" + url + "\n---TEXT---\nLangGraph tutorial\nLangGraph agents explained\nPython workflow video"
            if "reddit.com" in url:
                return "Reddit Search\n---URL---\n" + url + "\n---TEXT---\nAirAsia to Japan discussion\nCommon complaint: baggage fees\nSeveral users prefer morning flights"
            if "console.cloud.google.com" in url:
                return "Google Cloud Console\n---URL---\n" + url + "\n---TEXT---\nProject selector\nLogs Explorer\nCloud Run\nAPIs and Services"
            if "example.test/result" in url:
                return "Example Result\n---URL---\n" + url + "\n---TEXT---\nOpened result page"
            if "new+game+releases+in+2026" in url:
                return "Google Search\n---URL---\n" + url + "\n---TEXT---\nNew game releases in 2026\n2026 Confirmed Release Dates - Post State of Play! Reddit r/videogames\nGamesRadar release calendar"
            return "Google Search\n---URL---\n" + url + "\n---TEXT---\nModern kampung house\nTraditional Malay house design\nArchitectural reference"
        if "rawJson" in script:
            return '[{"kind":"a","label":"Example Result"},{"kind":"button","label":"Search"}]'
        if "visibleResult" in script:
            return "false"
        return ""


async def main() -> None:
    _require(route_browser_capability("search modern kampung house").child_skill == "google_search", "Google Search route failed")
    _require(route_browser_capability("google pokemon").child_skill == "google_search", "Google shorthand route failed")
    _require(route_browser_capability("search YouTube LangGraph tutorial").child_skill == "youtube_research", "YouTube route failed")
    _require(route_browser_capability("open first video").child_skill == "youtube_research", "YouTube follow-up route failed")
    _require(route_browser_capability("what does Reddit say about AirAsia Japan").child_skill == "reddit_research", "Reddit route failed")
    _require(route_browser_capability("open first thread").child_skill == "reddit_research", "Reddit follow-up route failed")
    _require(route_browser_capability("open Google Cloud Console").child_skill == "google_cloud_console", "GCP route failed")
    _require(_is_result_open_request("Maybe the Reddit one?"), "implicit Reddit result follow-up was not recognized")
    _require(_target_from_click_request("Maybe the Reddit one?").lower() == "reddit", "implicit Reddit follow-up target was not cleaned")

    with tempfile.TemporaryDirectory(prefix="maya-browser-site-skills-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        bridge = FakeBridge()

        reply = await run_browser_capability(db_path, "search modern kampung house", bridge=bridge)
        _require("Google Search skill used" in reply, "Google Search skill not used")
        _require(bridge.urls[-1] == "https://www.google.com/search?q=modern+kampung+house", "Google Search URL wrong")

        reply = await run_browser_capability(db_path, "search new game releases in 2026", bridge=bridge)
        _require("Google Search skill used" in reply, "new game search did not use Google Search")
        before = list(bridge.urls)
        reply = await run_browser_capability(db_path, "Maybe the Reddit one?", bridge=bridge)
        _require("Google Search skill opened a visible result" in reply, "implicit Reddit result follow-up did not open a Google result")
        _require(bridge.urls == before, "implicit Reddit result follow-up should not search Reddit for the literal phrase")

        reply = await run_browser_capability(db_path, "search YouTube LangGraph tutorial", bridge=bridge)
        _require("YouTube Research skill used" in reply, "YouTube skill not used")
        _require(bridge.urls[-1] == "https://www.youtube.com/results?search_query=LangGraph+tutorial", "YouTube URL wrong")

        reply = await run_browser_capability(db_path, "what does Reddit say about AirAsia Japan", bridge=bridge)
        _require("Reddit Research skill used" in reply, "Reddit skill not used")
        _require(bridge.urls[-1] == "https://www.reddit.com/search/?q=AirAsia+Japan", "Reddit URL wrong")

        reply = await run_browser_capability(db_path, "open Google Cloud logs", bridge=bridge)
        _require("Google Cloud Console skill opened logs" in reply, "GCP logs skill not used")
        _require(bridge.urls[-1] == "https://console.cloud.google.com/logs/query", "GCP logs URL wrong")

        before = list(bridge.urls)
        reply = await run_browser_capability(db_path, "delete Cloud Run service in Google Cloud", bridge=bridge)
        _require("read-only" in reply and "will not deploy, delete" in reply, "GCP unsafe action not blocked")
        _require(bridge.urls == before, "GCP unsafe action opened a new page")

        reply = await run_browser_capability(db_path, "open second result", bridge=bridge)
        _require("Google Search skill opened a visible result" in reply, "Google result open failed")

    print("browser_site_skills_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
