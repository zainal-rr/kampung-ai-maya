from __future__ import annotations

import re
from dataclasses import dataclass

from browser_control import note_browser_route
from browser_driver import make_browser_controller
from browser_site_skills import (
    run_google_cloud_console_skill,
    run_google_search_skill,
    run_reddit_research_skill,
    run_youtube_research_skill,
)
from browser_skill import run_browser_skill
from flight_search_skill import run_flight_search_skill
from frequent_sites import (
    find_frequent_site_request,
    frequent_site_catalog,
    should_use_specialized_site_skill,
)
from permission_policy import action_permission
from stay_booking_skill import run_airbnb_skill, run_booking_com_skill
from storage import upsert_preference
from utils import OSBridge


@dataclass(frozen=True)
class BrowserCapabilityRoute:
    child_skill: str
    reason: str
    site_id: str = ""
    site_name: str = ""
    site_url: str = ""
    site_policy: str = ""
    site_category: str = ""


async def run_browser_capability(db_path: str, request: str, *, bridge: OSBridge | None = None) -> str:
    route = route_browser_capability(request)
    note_browser_route(route.child_skill, route.reason)
    if route.child_skill == "google_images":
        return await run_browser_skill(db_path, request, bridge=bridge)
    if route.child_skill == "flight_search":
        return await run_flight_search_skill(db_path, request, fill=True, bridge=bridge)
    if route.child_skill == "airbnb_stay_search":
        return await run_airbnb_skill(db_path, request, bridge=bridge)
    if route.child_skill == "booking_com_hotel_search":
        return await run_booking_com_skill(db_path, request, bridge=bridge)
    if route.child_skill == "google_search":
        return await run_google_search_skill(db_path, request, bridge=bridge)
    if route.child_skill == "youtube_research":
        return await run_youtube_research_skill(db_path, request, bridge=bridge)
    if route.child_skill == "reddit_research":
        return await run_reddit_research_skill(db_path, request, bridge=bridge)
    if route.child_skill == "google_cloud_console":
        return await run_google_cloud_console_skill(db_path, request, bridge=bridge)
    if route.child_skill == "frequent_site_open":
        return await _open_frequent_site(db_path, route, bridge=bridge)
    return await run_browser_skill(db_path, request, bridge=bridge)


def route_browser_capability(request: str) -> BrowserCapabilityRoute:
    lowered = request.lower()
    if any(marker in lowered for marker in ("google image", "google images", "image search", "search images", "find images")):
        return BrowserCapabilityRoute("google_images", "image search marker")
    if _google_cloud_request(lowered):
        return BrowserCapabilityRoute("google_cloud_console", "Google Cloud Console marker")
    if _youtube_request(lowered):
        return BrowserCapabilityRoute("youtube_research", "YouTube marker")
    if _reddit_request(lowered):
        return BrowserCapabilityRoute("reddit_research", "Reddit marker")
    if "flight" in lowered or "flights" in lowered:
        return BrowserCapabilityRoute("flight_search", "flight keyword")
    if _search_result_open_request(lowered):
        return BrowserCapabilityRoute("google_search", "search result open marker")
    if _google_search_request(lowered):
        return BrowserCapabilityRoute("google_search", "Google search marker")
    site_match = find_frequent_site_request(request)
    if site_match and (should_use_specialized_site_skill(request, site_match.site) or _frequent_site_open_intent(request, site_match.site.domain)):
        site = site_match.site
        if should_use_specialized_site_skill(request, site):
            return BrowserCapabilityRoute(
                site.child_skill,
                f"{site_match.reason}; specialized search requested",
                site_id=site.id,
                site_name=site.name,
                site_url=site.base_url,
                site_policy=site.policy,
                site_category=site.category,
            )
        return BrowserCapabilityRoute(
            "frequent_site_open",
            site_match.reason,
            site_id=site.id,
            site_name=site.name,
            site_url=site.base_url,
            site_policy=site.policy,
            site_category=site.category,
        )
    if "airbnb" in lowered:
        return BrowserCapabilityRoute("airbnb_stay_search", "Airbnb keyword")
    if any(word in lowered for word in ("booking.com", "hotel", "hotels", "room", "rooms", "accommodation")):
        return BrowserCapabilityRoute("booking_com_hotel_search", "hotel or accommodation keyword")
    return BrowserCapabilityRoute("general_browser", "general browser request")


def _google_search_request(lowered: str) -> bool:
    if any(phrase in lowered for phrase in ("open google", "go to google", "visit google")):
        return False
    if re_match := re.search(r"^\s*(google|search|search for|look up|find online|check online)\s+\S+", lowered):
        return bool(re_match)
    return "google search" in lowered


def _search_result_open_request(lowered: str) -> bool:
    return bool(re.search(r"\b(open|click|select|choose)\b", lowered)) and any(
        marker in lowered for marker in ("result", "link", "first", "second", "third", "fourth", "fifth")
    )


def _youtube_request(lowered: str) -> bool:
    if "youtube" in lowered or "you tube" in lowered:
        return True
    return bool(re.search(r"\b(open|click|select|choose|search|find|look\s+for|summari[sz]e|recommend|check)\b", lowered)) and "video" in lowered


def _reddit_request(lowered: str) -> bool:
    if "reddit" in lowered or "subreddit" in lowered:
        return True
    return bool(re.search(r"\b(open|click|select|choose|search|find)\b", lowered)) and "thread" in lowered


def _google_cloud_request(lowered: str) -> bool:
    return any(marker in lowered for marker in ("google cloud", "gcp", "cloud console", "console.cloud.google.com"))


def _frequent_site_open_intent(request: str, domain: str) -> bool:
    lowered = request.lower()
    if domain in lowered:
        return True
    return any(
        phrase in lowered
        for phrase in (
            "open ",
            "go to ",
            "visit ",
            "show ",
            "launch ",
            "bring up ",
            "pull up ",
            "check ",
            "inspect ",
            "read ",
            "browse ",
        )
    )


def browser_child_skill_catalog() -> list[dict[str, str]]:
    skills = [
        {
            "id": "general_browser",
            "owner": "local browser control",
            "role": "Open Chrome, Google search, inspect pages, click safe targets, and fill non-sensitive fields.",
        },
        {
            "id": "google_images",
            "owner": "local browser control",
            "role": "Open Google Images directly for visual reference searches.",
        },
        {
            "id": "google_search",
            "owner": "local browser control + Gemini when page understanding is needed",
            "role": "Open clean Google searches, inspect result snippets, and open visible non-sensitive results by rank or title.",
        },
        {
            "id": "youtube_research",
            "owner": "local browser control + Gemini when video result understanding is needed",
            "role": "Search YouTube, inspect visible videos, and open videos by rank or title. Read-only by default.",
        },
        {
            "id": "reddit_research",
            "owner": "local browser control + Gemini when thread/comment synthesis is needed",
            "role": "Search Reddit, inspect visible threads/comments, and summarize community sentiment. Read-only by default.",
        },
        {
            "id": "google_cloud_console",
            "owner": "local browser control",
            "role": "Open and inspect Google Cloud Console read-only pages. Deploy/delete/restart/IAM/billing/key actions require approval.",
        },
        {
            "id": "flight_search",
            "owner": "local browser control + Gemini when itinerary/page understanding is needed",
            "role": "Open Google Flights, fill structured flight fields, read prices, and stop before booking/payment.",
        },
        {
            "id": "booking_com_hotel_search",
            "owner": "local browser control + Gemini when hotel comparison needs page understanding",
            "role": "Open Booking.com with structured stay fields, prefer mid-to-high range hotels, and stop before booking/payment.",
        },
        {
            "id": "airbnb_stay_search",
            "owner": "local browser control + Gemini when listing comparison needs page understanding",
            "role": "Open Airbnb with structured stay fields, prefer Guest Favourite when visible, and stop before reserve/payment.",
        },
        {
            "id": "frequent_site_open",
            "owner": "local browser control",
            "role": "Open frequently used sites by canonical URL with category-specific safety boundaries.",
        },
        {
            "id": "ai_dashboard_open",
            "owner": "local browser control",
            "role": "Open AI and developer dashboards; inspect only unless Zainal gives an explicit safe action.",
        },
        {
            "id": "research_site_open",
            "owner": "local browser control",
            "role": "Open research and reference sites for visible-page reading and non-sensitive navigation.",
        },
        {
            "id": "travel_site_open",
            "owner": "local browser control + Gemini when option comparison needs page understanding",
            "role": "Open travel sites for research and comparison; stop before booking or payment.",
        },
        {
            "id": "local_dashboard_open",
            "owner": "local browser control",
            "role": "Open local or configured internal dashboards; no destructive admin actions.",
        },
        {
            "id": "communication_site_open",
            "owner": "local browser control",
            "role": "Open communication sites only when requested; no sends, deletes, or private exposure without explicit instruction.",
        },
        {
            "id": "sensitive_site_open",
            "owner": "local browser control",
            "role": "Open sensitive sites only; never read, fill, reveal, submit, or store credentials, OTPs, cards, bank data, or private keys.",
        },
    ]
    skills.extend(
        {
            "id": f"frequent_site:{site['id']}",
            "owner": "frequent site registry",
            "role": f"{site['name']} ({site['domain']}): {site['policy']}",
        }
        for site in frequent_site_catalog()
    )
    return skills


async def _open_frequent_site(db_path: str, route: BrowserCapabilityRoute, *, bridge: OSBridge | None = None) -> str:
    permission = "travel_search" if route.site_category == "travel" else "browse_web"
    if action_permission(permission) != "allow":
        return "I need your confirmation before opening that site."
    browser = make_browser_controller(bridge)
    browser.open_new_tab_url(route.site_url)
    await upsert_preference(db_path, "maya_active_workflow", f"browser:site:{route.site_id}:{route.site_url}", source="skill")
    boundary = f" Boundary: {route.site_policy}" if route.site_policy else ""
    sensitive_categories = {"sensitive_finance", "communication_sensitive"}
    sensitive_note = " Sensitive mode is active." if route.site_category in sensitive_categories or "sensitive" in route.child_skill else ""
    return f"Browser capability opened {route.site_name}: {route.site_url}.{sensitive_note}{boundary}"
