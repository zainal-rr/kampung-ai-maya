from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

from browser_control import note_browser_intent, page_summary
from browser_driver import make_browser_controller
from browser_site_skill_helpers import (
    _clean_site_query,
    _extract_visible_options,
    _gcp_url_for_request,
    _is_result_open_request,
    _looks_like_posting_or_account_action,
    _options_match_target,
    _rank_from_text,
    _sensitive_browser_action,
    _sensitive_page,
    _target_from_click_request,
    _unsafe_gcp_action,
)
from browser_understanding import extract_browser_options_with_gemini, grounded_browser_options
from permission_policy import action_permission
from skill_store import init_skill_db, record_skill_usage, upsert_skill
from storage import get_preference, upsert_preference
from utils import OSBridge


GOOGLE_SEARCH_SKILL_ID = "google_search"
GOOGLE_SEARCH_SKILL_NAME = "Google Search"
YOUTUBE_SKILL_ID = "youtube_research"
YOUTUBE_SKILL_NAME = "YouTube Research"
REDDIT_SKILL_ID = "reddit_research"
REDDIT_SKILL_NAME = "Reddit Research"
GCP_SKILL_ID = "google_cloud_console"
GCP_SKILL_NAME = "Google Cloud Console"


@dataclass(frozen=True)
class SiteSkillSpec:
    skill_id: str
    name: str
    base_url: str
    search_url_prefix: str
    workflow_prefix: str
    description: str
    provider_name: str
    fallback_search_url_prefix: str = ""


GOOGLE_SPEC = SiteSkillSpec(
    GOOGLE_SEARCH_SKILL_ID,
    GOOGLE_SEARCH_SKILL_NAME,
    "https://www.google.com",
    "https://www.google.com/search?q=",
    "google_search",
    "Search Google, inspect result snippets, and open visible non-sensitive results.",
    "Google Search",
)
YOUTUBE_SPEC = SiteSkillSpec(
    YOUTUBE_SKILL_ID,
    YOUTUBE_SKILL_NAME,
    "https://www.youtube.com",
    "https://www.youtube.com/results?search_query=",
    "youtube",
    "Search YouTube, inspect visible video results, and open visible videos by rank or title.",
    "YouTube",
)
REDDIT_SPEC = SiteSkillSpec(
    REDDIT_SKILL_ID,
    REDDIT_SKILL_NAME,
    "https://www.reddit.com",
    "https://www.reddit.com/search/?q=",
    "reddit",
    "Search Reddit, inspect visible threads and comments, and summarize common community signals.",
    "Reddit",
    fallback_search_url_prefix="https://old.reddit.com/search?q=",
)


class SearchSiteSkill:
    def __init__(self, db_path: str, spec: SiteSkillSpec, bridge: OSBridge | None = None):
        self.db_path = db_path
        self.spec = spec
        self.bridge = bridge or OSBridge()
        self.browser = make_browser_controller(bridge)

    async def run(self, request: str) -> str:
        if action_permission("browse_web") != "allow":
            return f"I need your confirmation before using {self.spec.name}."
        await self._record_skill(request)
        if _looks_like_posting_or_account_action(request):
            return f"{self.spec.name} is read-only by default. I will not post, vote, comment, subscribe, message, or change account settings."
        if _is_result_open_request(request):
            return await self._open_result(request)
        query = _clean_site_query(request, self.spec.skill_id)
        if not query:
            return await self._open_home()
        return await self._search(query)

    async def _open_home(self) -> str:
        await asyncio.to_thread(self.browser.open_new_tab_url, self.spec.base_url)
        await upsert_preference(self.db_path, "maya_active_workflow", f"browser:{self.spec.workflow_prefix}:home", source="skill")
        return f"{self.spec.name} skill opened {self.spec.base_url}."

    async def _search(self, query: str) -> str:
        note_browser_intent({"query": query})
        url = self.spec.search_url_prefix + quote_plus(query)
        page, options = await self._search_once(url, query)
        fallback_note = ""
        if not options and self.spec.fallback_search_url_prefix:
            url = self.spec.fallback_search_url_prefix + quote_plus(query)
            page, options = await self._search_once(url, query)
            fallback_note = f"note: the main {self.spec.name} page gave no readable results, so I retried on {url.split('/search')[0]}."
        await upsert_preference(self.db_path, "maya_active_workflow", f"browser:{self.spec.workflow_prefix}:search:{query}", source="skill")
        reply = _search_reply(self.spec, query, page.url or url, options, page.title)
        return f"{reply}\n{fallback_note}" if fallback_note else reply

    async def _wait_for_results(self, attempts: int = 6) -> list[str]:
        for _ in range(attempts):
            options = await _safe_result_options(self.browser)
            if options:
                return options
            await asyncio.sleep(1.0)
        return []

    async def _last_search_query(self) -> str:
        raw = await get_preference(self.db_path, "maya_active_workflow") or ""
        prefix = f"browser:{self.spec.workflow_prefix}:search:"
        return raw[len(prefix):] if raw.startswith(prefix) else ""

    async def _search_once(self, url: str, query: str):
        await asyncio.to_thread(self.browser.open_new_tab_url, url)
        await asyncio.to_thread(time.sleep, 1.0)
        page = await _safe_inspect(self.browser, max_chars=10000)
        options = await _safe_result_options(self.browser)
        if not options:
            options = _extract_visible_options(page.text)
        if not options:
            options = await extract_browser_options_with_gemini(
                self.db_path,
                provider=self.spec.provider_name,
                goal=query,
                page_title=page.title,
                page_url=page.url or url,
                page_text=page.text,
            )
            options = grounded_browser_options(options, page.text)
        return page, options

    async def _open_result(self, request: str) -> str:
        rank = _rank_from_text(request)
        target = _target_from_click_request(request)
        note_browser_intent({"open_rank": rank, "open_target": target})
        if _sensitive_browser_action(request):
            return "This browser action looks sensitive. I will stop before login, payment, private data, posting, or account changes."
        recovery_note = ""
        visible = await _safe_result_options(self.browser)
        recovery_query = ""
        if target and not _options_match_target(visible, target):
            recovery_query = target
        elif not visible:
            recovery_query = await self._last_search_query()
            if not recovery_query:
                return (
                    f"{self.spec.name} skill has no results page open and no previous "
                    f"{self.spec.name} search to reopen. Tell me what to search first."
                )
        if recovery_query:
            await self._search_once(self.spec.search_url_prefix + quote_plus(recovery_query), recovery_query)
            recovery_note = f"note: no matching results were on screen, so I searched '{recovery_query}' again first."
            await self._wait_for_results()
        try:
            raw = await asyncio.to_thread(self.browser.click_search_result, target, rank)
            if not raw.startswith("CLICKED_RESULT:") and target:
                raw = await asyncio.to_thread(self.browser.click_search_result, "", rank)
            if not raw.startswith("CLICKED_RESULT:"):
                # Results pages render late on SPA sites; wait once and retry.
                await self._wait_for_results()
                raw = await asyncio.to_thread(self.browser.click_search_result, "", rank)
            await asyncio.to_thread(time.sleep, 1.0)
            page = await _safe_inspect(self.browser, max_chars=5000)
        except Exception as exc:
            return f"{self.spec.name} skill could not open that result yet: {exc}"
        if not raw.startswith("CLICKED_RESULT:"):
            return f"{self.spec.name} skill could not find a visible result matching that request."
        await upsert_preference(self.db_path, "maya_active_workflow", f"browser:{self.spec.workflow_prefix}:opened_result:{rank}", source="skill")
        if _sensitive_page(page.text, page.url):
            return f"{self.spec.name} skill opened a result, but I am stopping because the page looks sensitive.\nURL: {page.url}"
        lines = [
            f"{self.spec.name} skill opened a visible result.",
            f"clicked: {raw.split(':', 1)[1].strip()}",
        ]
        if recovery_note:
            lines.append(recovery_note)
        lines.append(page_summary(page, max_lines=6))
        return "\n".join(lines)

    async def _record_skill(self, request: str) -> None:
        await _record_site_skill(self.db_path, self.spec.skill_id, self.spec.name, self.spec.description, request, f"iMac {self.spec.workflow_prefix}_skill")


class GoogleCloudConsoleSkill:
    def __init__(self, db_path: str, bridge: OSBridge | None = None):
        self.db_path = db_path
        self.bridge = bridge or OSBridge()
        self.browser = make_browser_controller(bridge)

    async def run(self, request: str) -> str:
        if action_permission("gcp_use") != "allow" and action_permission("browse_web") != "allow":
            return "I need your confirmation before opening Google Cloud Console."
        await _record_site_skill(
            self.db_path,
            GCP_SKILL_ID,
            GCP_SKILL_NAME,
            "Open and inspect Google Cloud Console read-only pages; block deploys, deletes, IAM, billing changes, and credentials.",
            request,
            "iMac google_cloud_console_skill",
        )
        if _unsafe_gcp_action(request):
            return (
                "Google Cloud Console skill is read-only for this request. "
                "I will not deploy, delete, restart, change IAM, change billing, create keys, or expose credentials without explicit approval."
            )
        url, purpose = _gcp_url_for_request(request)
        await asyncio.to_thread(self.browser.open_new_tab_url, url)
        await asyncio.to_thread(time.sleep, 1.0)
        page = await _safe_inspect(self.browser, max_chars=8000)
        await upsert_preference(self.db_path, "maya_active_workflow", f"browser:gcp:{purpose}:{url}", source="skill")
        return (
            f"Google Cloud Console skill opened {purpose} in read-only mode.\n"
            f"url: {url}\n"
            + page_summary(page, max_lines=6)
        )


async def run_google_search_skill(db_path: str, request: str, *, bridge: OSBridge | None = None) -> str:
    return await SearchSiteSkill(db_path, GOOGLE_SPEC, bridge).run(request)


async def run_youtube_research_skill(db_path: str, request: str, *, bridge: OSBridge | None = None) -> str:
    return await SearchSiteSkill(db_path, YOUTUBE_SPEC, bridge).run(request)


async def run_reddit_research_skill(db_path: str, request: str, *, bridge: OSBridge | None = None) -> str:
    return await SearchSiteSkill(db_path, REDDIT_SPEC, bridge).run(request)


async def run_google_cloud_console_skill(db_path: str, request: str, *, bridge: OSBridge | None = None) -> str:
    return await GoogleCloudConsoleSkill(db_path, bridge).run(request)


async def _record_site_skill(db_path: str, skill_id: str, name: str, description: str, request: str, lane: str) -> None:
    await init_skill_db(db_path)
    scaffold = Path(__file__).resolve().parent / "maya_skills" / "active" / f"{skill_id}.md"
    await upsert_skill(db_path, skill_id, name, description, "bounded", "policy_guard", "active", "local", str(scaffold))
    await record_skill_usage(db_path, skill_id=skill_id, name=name, query=request, lane=lane, reason="browser capability routed to executable site skill")


async def _safe_inspect(browser, *, max_chars: int):
    try:
        return await asyncio.to_thread(browser.inspect_page, max_chars)
    except Exception:
        from browser_control import BrowserPage

        return BrowserPage("", "", "")


async def _safe_result_options(browser) -> list[str]:
    try:
        return await asyncio.to_thread(browser.inspect_search_results, 8)
    except Exception:
        return []


def _search_reply(spec: SiteSkillSpec, query: str, url: str, options: list[str], title: str) -> str:
    lines = [
        f"{spec.name} skill used.",
        f"query: {query}",
        f"url: {url}",
    ]
    if title:
        lines.append(f"title: {title}")
    if options:
        label = "visible results"
        if spec.skill_id == REDDIT_SKILL_ID:
            label = "visible community signals"
        elif spec.skill_id == YOUTUBE_SKILL_ID:
            label = "visible videos"
        lines.append(f"{label}:")
        lines.extend(f"{idx}) {item}" for idx, item in enumerate(options[:5], 1))
    else:
        lines.append("visible results: none extracted from page text yet.")
    return "\n".join(lines)


















