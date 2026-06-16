from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

import browser_skill
import maya_browser.site_runtime as browser_site_runtime
from browser_capability import browser_child_skill_catalog, route_browser_capability, run_browser_capability
from storage import init_db


class FakeBridge:
    def __init__(self):
        self.urls: list[str] = []
        self.typed: list[str] = []

    def get_frontmost_app(self) -> str:
        return "Google Chrome"

    def open_url_new_tab(self, url: str, app_name: str = "Google Chrome") -> None:
        self.urls.append(url)

    def open_url(self, url: str, app_name: str = "Google Chrome") -> None:
        self.urls.append(url)

    def press_shortcut(self, shortcut: str) -> None:
        pass

    def type_text(self, text: str) -> None:
        self.typed.append(text)

    def _run_applescript(self, script: str) -> str:
        if "rawJson" in script:
            labels = ["One way", "Federal Territory of Kuala Lumpur", "Where to?", "Penang", "Sun, Jun 7", "Search"]
            return json.dumps([{"kind": "input", "label": label} for label in labels])
        if "clickResult" in script:
            return "CLICKED: Search"
        if "pageTitle" in script:
            return "Browser Page\n---URL---\nhttps://example.test\n---TEXT---\nPenang RM250\nGuest favourite RM420"
        return json.dumps({
            "title": "Current Itinerary",
            "url": "https://example.test/itinerary",
            "selection": "",
            "anchor": "",
            "nearby": "Trip to Penang on June 7 2026",
            "headings": "Penang",
            "page": "Trip to Penang on June 7 2026",
            "hidden": "",
        })


async def main() -> None:
    _require(route_browser_capability("find flight to Penang June 7").child_skill == "flight_search", "flight route failed")
    _require(route_browser_capability("find Airbnb in Penang").child_skill == "airbnb_stay_search", "airbnb route failed")
    _require(route_browser_capability("find hotel in Penang").child_skill == "booking_com_hotel_search", "hotel route failed")
    _require(route_browser_capability("google images modern kampung house").child_skill == "google_images", "image route failed")
    _require(route_browser_capability("search modern kampung house").child_skill == "google_search", "google search route failed")
    _require(route_browser_capability("Google search best video games 2026 so far").child_skill == "google_search", "explicit Google search should not be hijacked by video/YouTube routing")
    _require(route_browser_capability("search YouTube LangGraph tutorial").child_skill == "youtube_research", "youtube route failed")
    _require(route_browser_capability("what does Reddit say about AirAsia").child_skill == "reddit_research", "reddit route failed")
    reddit_followup = route_browser_capability("Maybe the Reddit one?")
    _require(reddit_followup.child_skill == "google_search", "site-result follow-up should use Google result opening")
    _require(reddit_followup.reason == "site result follow-up marker", "site-result follow-up route reason changed")
    open_reddit_followup = route_browser_capability("can you open the Reddit?")
    _require(open_reddit_followup.child_skill == "google_search", "the Reddit follow-up should use Google result opening")
    open_tripadvisor_followup = route_browser_capability("open the Tripadvisor one")
    _require(open_tripadvisor_followup.child_skill == "google_search", "the Tripadvisor follow-up should use Google result opening")
    _require(route_browser_capability("open Google Cloud Console").child_skill == "google_cloud_console", "gcp route failed")
    _require(route_browser_capability("open github").child_skill == "frequent_site_open", "frequent site route failed")
    _require(route_browser_capability("open maybank").site_category == "sensitive_finance", "sensitive site route failed")
    _require(
        route_browser_capability("Open the Reddit thread at https://www.reddit.com/r/bali/comments/153fwaa/best_beach_area_in_seminyak/").child_skill
        == "general_browser",
        "direct Reddit URL should open through general browser navigation",
    )
    _require(
        route_browser_capability("https://www.wanderlustchloe.com/things-to-do-langkawi-malaysia/").child_skill
        == "general_browser",
        "bare URL should open through general browser navigation",
    )
    _require(route_browser_capability("google pokemon").child_skill == "google_search", "plain Google query should use google search skill")
    _require(route_browser_capability("open the Metacritic page for The Witcher 3").child_skill == "google_search", "named page open should search")
    _require(route_browser_capability("open Chrome").child_skill == "general_browser", "general route failed")
    catalog = browser_child_skill_catalog()
    _require({item["id"] for item in catalog} >= {"general_browser", "google_images", "google_search", "youtube_research", "reddit_research", "google_cloud_console", "flight_search", "booking_com_hotel_search", "airbnb_stay_search", "frequent_site_open"}, "catalog missing child skills")

    with tempfile.TemporaryDirectory(prefix="maya-browser-capability-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        bridge = FakeBridge()

        reply = await run_browser_capability(db_path, "google images modern kampung house", bridge=bridge)
        _require("Google Images" in reply, "google images did not run")
        _require("udm=2" in bridge.urls[-1], "google images URL missing image mode")

        before = len(bridge.urls)
        reply = await run_browser_capability(db_path, "search a Google image", bridge=bridge)
        _require("What image topic" in reply, "missing image topic should ask a clarification")
        _require(len(bridge.urls) == before, "missing image topic must not open a literal search")

        reply = await run_browser_capability(db_path, "what are you searching?", bridge=bridge)
        _require("Browser skill inspected Chrome" in reply, "status question should not become image topic")
        _require(len(bridge.urls) == before, "status question should not consume pending image topic")

        reply = await run_browser_capability(db_path, "Nasi lemak?", bridge=bridge)
        _require("Google Images" in reply, "pending image clarification should run Google Images")
        _require("q=Nasi+lemak" in bridge.urls[-1], f"pending image topic used wrong URL: {bridge.urls[-1]}")

        reply = await run_browser_capability(db_path, "Can you gind a Google image of nasi lemak", bridge=bridge)
        _require("Google Images" in reply, "misspelled image request should run Google Images")
        _require("q=nasi+lemak" in bridge.urls[-1], f"misspelled image request used wrong URL: {bridge.urls[-1]}")

        reply = await run_browser_capability(db_path, "Can you Google say modern kampung house", bridge=bridge)
        _require("Google Search skill used" in reply, "misheard Google search should run Google Search")
        _require("modern+kampung+house" in bridge.urls[-1], f"misheard Google search used wrong URL: {bridge.urls[-1]}")

        reply = await run_browser_capability(db_path, "Google search best video games 2026 so far", bridge=bridge)
        _require("Google Search skill used" in reply, "explicit Google search with video games should run Google Search")
        _require("google.com/search" in bridge.urls[-1], f"video-game Google request was not a Google search: {bridge.urls[-1]}")
        _require("youtube.com" not in bridge.urls[-1], f"video-game Google request was hijacked to YouTube: {bridge.urls[-1]}")

        reply = await run_browser_capability(db_path, "https://www.wanderlustchloe.com/things-to-do-langkawi-malaysia/", bridge=bridge)
        _require("opened this URL" in reply, f"bare URL did not navigate: {reply}")
        _require(
            bridge.urls[-1] == "https://www.wanderlustchloe.com/things-to-do-langkawi-malaysia/",
            f"bare URL opened wrong target: {bridge.urls[-1]}",
        )

        reply = await run_browser_capability(db_path, "find flight to Penang June 7 2026", bridge=bridge)
        _require("Flight search skill used" in reply, "flight child skill did not run")
        _require(bridge.urls[-1] == "https://www.google.com/travel/flights", "flight child did not open stable URL")

        reply = await run_browser_capability(db_path, "open github", bridge=bridge)
        _require("Browser capability opened GitHub" in reply, "frequent site open did not run")
        _require(bridge.urls[-1] == "https://github.com", "frequent site opened wrong URL")

        reddit_url = "https://www.reddit.com/r/bali/comments/153fwaa/best_beach_area_in_seminyak/"
        reply = await run_browser_capability(db_path, f"Open the Reddit thread at {reddit_url}", bridge=bridge)
        _require("Browser skill opened this URL in Chrome" in reply, "direct Reddit URL should open as read-only navigation")
        _require(bridge.urls[-1] == reddit_url, "direct Reddit URL opened wrong URL")

        reply = await run_browser_capability(db_path, "open the Metacritic page for The Witcher 3", bridge=bridge)
        _require("Google Search skill used" in reply, "named page open did not use Google Search")
        _require("Metacritic+page+for+The+Witcher+3" in bridge.urls[-1], "named page query was not cleaned/opened")

    with tempfile.TemporaryDirectory(prefix="maya-browser-lazy-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        original_site = browser_site_runtime.make_browser_controller
        original_general = browser_skill.make_browser_controller

        def fail_controller(*_args, **_kwargs):
            raise AssertionError("browser controller should not start for incomplete queries")

        browser_site_runtime.make_browser_controller = fail_controller
        browser_skill.make_browser_controller = fail_controller
        try:
            reply = await run_browser_capability(db_path, "Can you Google say")
            _require(reply == "What should I search for on Google Search?", "misheard incomplete Google phrase should ask for a topic")
            reply = await run_browser_capability(db_path, "Google search uh the")
            _require(reply == "What should I search for on Google Search?", "incomplete Google search should not start Chrome")
        finally:
            browser_site_runtime.make_browser_controller = original_site
            browser_skill.make_browser_controller = original_general

    print("browser_capability_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
