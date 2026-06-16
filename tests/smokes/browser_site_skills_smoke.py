from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import os
import tempfile
from pathlib import Path

from maya_browser.browser_capability import route_browser_capability, run_browser_capability
from maya_browser.browser_site_skill_helpers import _is_result_open_request, _target_from_click_request
from storage import init_db


class FakeBridge:
    def __init__(self):
        self.urls: list[str] = []
        self.force_bad_reddit_search = False

    def open_url_new_tab(self, url: str, app_name: str = "Google Chrome") -> None:
        self.urls.append(url)

    def open_url(self, url: str, app_name: str = "Google Chrome") -> None:
        self.urls.append(url)

    def _run_applescript(self, script: str) -> str:
        if "CLICKED_RESULT" in script:
            if "tripadvisor" in script.lower() or (self.urls and "tripadvisor." in self.urls[-1]):
                url = "https://www.tripadvisor.com.my/HotelsList-Pulau_Redang-Beach-Resorts-zfp132764.html"
                self.urls.append(url)
                return "CLICKED_RESULT: THE 10 BEST Pulau Redang Beach Resorts | " + url
            if "reddit" in script.lower() or (self.urls and "reddit.com" in self.urls[-1]):
                if self.force_bad_reddit_search:
                    url = "https://www.reddit.com/search/?q=Can+I%2C+open+the+Reddit%3F"
                    self.urls.append(url)
                    return "CLICKED_RESULT: Can I, open the Reddit? | " + url
                if self.urls and "new+game+releases+in+2026" in self.urls[-1]:
                    url = "https://www.reddit.com/r/videogames/comments/abc/2026_game_releases/"
                    self.urls.append(url)
                    return "CLICKED_RESULT: 2026 game releases Reddit discussion | " + url
                url = "https://www.reddit.com/r/witcher/comments/abc/the_witcher_3_review_thread/"
                self.urls.append(url)
                return "CLICKED_RESULT: The Witcher 3 review Reddit discussion | " + url
            return "CLICKED_RESULT: Example Result | https://example.test/result"
        if "pageTitle" in script:
            url = self.urls[-1] if self.urls else "https://example.test"
            if "youtube.com" in url:
                return "YouTube Search\n---URL---\n" + url + "\n---TEXT---\nLangGraph tutorial\nLangGraph agents explained\nPython workflow video"
            if "reddit.com" in url:
                if "Can+I%2C+open+the+Reddit" in url:
                    return "Can I, open the Reddit? - Reddit Search!\n---URL---\n" + url + "\n---TEXT---\nReddit search results for Can I, open the Reddit?"
                if "2026_game_releases" in url:
                    return "2026 game releases discussion - Reddit\n---URL---\n" + url + "\n---TEXT---\nReddit users discuss new game releases in 2026."
                if "witcher" in url:
                    return "The Witcher 3 review thread - Reddit\n---URL---\n" + url + "\n---TEXT---\nPlayers discuss The Witcher 3 review scores and long-term impressions."
                return "Reddit Search\n---URL---\n" + url + "\n---TEXT---\nAirAsia to Japan discussion\nCommon complaint: baggage fees\nSeveral users prefer morning flights"
            if "tripadvisor." in url:
                return "THE 10 BEST Pulau Redang Beach Resorts - Tripadvisor\n---URL---\n" + url + "\n---TEXT---\nPulau Redang beach resorts and Redang Island Malaysia hotels near beaches."
            if "console.cloud.google.com" in url:
                return "Google Cloud Console\n---URL---\n" + url + "\n---TEXT---\nProject selector\nLogs Explorer\nCloud Run\nAPIs and Services"
            if "example.test/result" in url:
                return "Example Result\n---URL---\n" + url + "\n---TEXT---\nOpened result page"
            if "Witcher+3+review" in url or "witcher+3+review" in url:
                return "Google Search\n---URL---\n" + url + "\n---TEXT---\nThe Witcher 3 review\nThe Witcher 3 review Reddit discussion | https://www.reddit.com/r/witcher/comments/abc/the_witcher_3_review_thread/\nIGN The Witcher 3 review"
            if "new+game+releases+in+2026" in url:
                return "Google Search\n---URL---\n" + url + "\n---TEXT---\nNew game releases in 2026\n2026 Confirmed Release Dates - Post State of Play! Reddit r/videogames\nGamesRadar release calendar"
            if "Redang+island+Malaysia+beaches+resorts" in url:
                return "Google Search\n---URL---\n" + url + "\n---TEXT---\nRedang Island Malaysia beaches resorts\nTHE 10 BEST Pulau Redang Beach Resorts | https://www.tripadvisor.com.my/HotelsList-Pulau_Redang-Beach-Resorts-zfp132764.html\nRedang Island resort guide"
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
    _require(
        route_browser_capability("Open https://www.tripadvisor.com.my/Attractions-g469404-Activities-c61-t52-Seminyak_Kuta_District_Bali.html").child_skill
        == "general_browser",
        "direct URL open should bypass site/search routing",
    )
    _require(_is_result_open_request("Maybe the Reddit one?"), "implicit Reddit result follow-up was not recognized")
    _require(_target_from_click_request("Maybe the Reddit one?").lower() == "reddit", "implicit Reddit follow-up target was not cleaned")
    _require(_is_result_open_request("can you open the Reddit?"), "the Reddit follow-up was not recognized")
    _require(_target_from_click_request("can you open the Reddit?").lower() == "reddit", "the Reddit target was not cleaned")
    _require(_is_result_open_request("open the Tripadvisor one"), "the Tripadvisor follow-up was not recognized")
    _require(_target_from_click_request("open the Tripadvisor one").lower() == "tripadvisor", "the Tripadvisor target was not cleaned")

    old_mode = os.environ.get("MAYA_BROWSER_MODE")
    old_wait = os.environ.get("MAYA_BROWSER_EXTENSION_WAIT_SECONDS")
    try:
        os.environ["MAYA_BROWSER_MODE"] = "extension_strict"
        os.environ["MAYA_BROWSER_EXTENSION_WAIT_SECONDS"] = "0"
        with tempfile.TemporaryDirectory(prefix="maya-browser-site-strict-") as tmp:
            db_path = str(Path(tmp) / "smoke.db")
            await init_db(db_path)
            try:
                await run_browser_capability(db_path, "search modern kampung house")
            except RuntimeError as exc:
                _require("extension is not connected" in str(exc), "strict mode failure message changed")
            else:
                raise AssertionError("strict browser path silently fell back without an injected bridge")
    finally:
        if old_mode is None:
            os.environ.pop("MAYA_BROWSER_MODE", None)
        else:
            os.environ["MAYA_BROWSER_MODE"] = old_mode
        if old_wait is None:
            os.environ.pop("MAYA_BROWSER_EXTENSION_WAIT_SECONDS", None)
        else:
            os.environ["MAYA_BROWSER_EXTENSION_WAIT_SECONDS"] = old_wait

    with tempfile.TemporaryDirectory(prefix="maya-browser-site-skills-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        bridge = FakeBridge()

        reply = await run_browser_capability(db_path, "search modern kampung house", bridge=bridge)
        _require("Google Search skill used" in reply, "Google Search skill not used")
        _require(bridge.urls[-1] == "https://www.google.com/search?q=modern+kampung+house", "Google Search URL wrong")

        reply = await run_browser_capability(db_path, "Can you Google say modern kampung house", bridge=bridge)
        _require("Google Search skill used" in reply, "misheard Google search should use Google Search")
        _require(bridge.urls[-1] == "https://www.google.com/search?q=modern+kampung+house", "misheard Google search URL wrong")

        before = len(bridge.urls)
        reply = await run_browser_capability(db_path, "Uh, no, I want to, I want you to Google search, uh, the", bridge=bridge)
        _require(reply == "What should I search for on Google Search?", "incomplete spoken Google search should ask for a topic")
        _require(len(bridge.urls) == before, "incomplete spoken Google search must not open a literal URL")

        reply = await run_browser_capability(db_path, "search new game releases in 2026", bridge=bridge)
        _require("Google Search skill used" in reply, "new game search did not use Google Search")
        before = list(bridge.urls)
        reply = await run_browser_capability(db_path, "Maybe the Reddit one?", bridge=bridge)
        _require("Google Search skill opened a visible result" in reply, "implicit Reddit result follow-up did not open a Google result")
        _require(bridge.urls[: len(before)] == before, "implicit Reddit result follow-up should keep the original search history")
        _require("reddit.com/r/videogames/comments" in bridge.urls[-1], "implicit Reddit result follow-up should open a Reddit result")

        reply = await run_browser_capability(db_path, "search Witcher 3 review", bridge=bridge)
        _require("Google Search skill used" in reply, "Witcher review search did not use Google Search")
        reply = await run_browser_capability(db_path, "can you open the Reddit?", bridge=bridge)
        _require("Google Search skill opened a visible result" in reply, "the Reddit follow-up did not open the contextual result")
        _require("reddit.com/r/witcher/comments" in bridge.urls[-1], "the Reddit follow-up opened the wrong URL")
        _require("Can+I%2C+open+the+Reddit" not in bridge.urls[-1], "the Reddit follow-up searched the literal phrase")
        reply = await run_browser_capability(db_path, "click the first post on the current Reddit review search page", bridge=bridge)
        _require("read-only by default" not in reply, "clicking a visible Reddit post result should not be treated as posting")
        _require("opened a visible result" in reply, "clicking the first Reddit post should open a visible result")

        reply = await run_browser_capability(db_path, "search Redang island Malaysia beaches resorts", bridge=bridge)
        _require("Google Search skill used" in reply, "Redang search did not use Google Search")
        reply = await run_browser_capability(db_path, "open the Tripadvisor one", bridge=bridge)
        _require("Google Search skill opened a visible result" in reply, "the Tripadvisor follow-up did not open the contextual result")
        _require("tripadvisor.com.my/HotelsList-Pulau_Redang-Beach-Resorts-zfp132764" in bridge.urls[-1], "the Tripadvisor follow-up opened the wrong URL")

        reddit_url = "https://www.reddit.com/r/bali/comments/153fwaa/best_beach_area_in_seminyak/"
        reply = await run_browser_capability(db_path, f"Open the Reddit thread at {reddit_url}", bridge=bridge)
        _require("Browser skill opened this URL in Chrome" in reply, "Reddit thread URL should open as read-only navigation")
        _require(bridge.urls[-1] == reddit_url, "Reddit thread URL was not opened directly")

        tripadvisor_url = "https://www.tripadvisor.com.my/Attractions-g469404-Activities-c61-t52-Seminyak_Kuta_District_Bali.html"
        reply = await run_browser_capability(db_path, f"Open the Tripadvisor page for best Seminyak beaches at {tripadvisor_url}", bridge=bridge)
        _require("Browser skill opened this URL in Chrome" in reply, "URL-bearing Tripadvisor request should open directly")
        _require(bridge.urls[-1] == tripadvisor_url, "Tripadvisor URL was searched instead of opened")

        reply = await run_browser_capability(db_path, "search Witcher 3 review", bridge=bridge)
        _require("Google Search skill used" in reply, "Witcher review context reset did not use Google Search")
        bridge.force_bad_reddit_search = True
        reply = await run_browser_capability(db_path, "can you open the Reddit?", bridge=bridge)
        _require("could not verify" in reply and "site search page" in reply, "literal Reddit search page was not rejected")
        bridge.force_bad_reddit_search = False

    with tempfile.TemporaryDirectory(prefix="maya-browser-site-no-context-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        bridge = FakeBridge()
        reply = await run_browser_capability(db_path, "can you open the Reddit review?", bridge=bridge)
        _require("no active search result context" in reply, "contextual Reddit follow-up should ask without context")
        reply = await run_browser_capability(db_path, "open the Tripadvisor one", bridge=bridge)
        _require("no active search result context" in reply, "contextual Tripadvisor follow-up should ask without context")
        reply = await run_browser_capability(db_path, "open Reddit", bridge=bridge)
        _require("Reddit Research skill opened https://www.reddit.com" in reply, "plain open Reddit should open Reddit home")

        reply = await run_browser_capability(db_path, "search YouTube LangGraph tutorial", bridge=bridge)
        _require("YouTube Research skill used" in reply, "YouTube skill not used")
        _require(bridge.urls[-1] == "https://www.youtube.com/results?search_query=LangGraph+tutorial", "YouTube URL wrong")

        reply = await run_browser_capability(db_path, "what does Reddit say about AirAsia Japan", bridge=bridge)
        _require("Reddit Research skill used" in reply, "Reddit skill not used")
        _require(bridge.urls[-1] == "https://www.reddit.com/search/?q=AirAsia+Japan", "Reddit URL wrong")

        reply = await run_browser_capability(db_path, "yes please", bridge=bridge)
        _require("Reddit Research skill opened a visible result" in reply, "pending Reddit confirmation did not open a thread")
        _require("reddit.com/" in bridge.urls[-1], "pending Reddit confirmation opened the wrong URL")

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
