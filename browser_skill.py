from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

from browser_control import BrowserPage, element_summary, note_browser_intent, page_summary
from browser_driver import make_browser_controller
from browser_site_skill_helpers import _extract_visible_options
from browser_untrusted_guard import injected_page_action_notice
from permission_policy import action_permission, contains_sensitive_info, hard_no_private_exposure_text
from skill_store import init_skill_db, record_skill_usage, upsert_skill
from storage import upsert_preference
from utils import OSBridge


SKILL_ID = "browser_control"
SKILL_NAME = "Browser Control"
GOOGLE_HOME = "https://www.google.com"


@dataclass(frozen=True)
class BrowserSkillIntent:
    action: str
    target: str = ""
    value: str = ""


class BrowserSkill:
    def __init__(self, db_path: str, bridge: OSBridge | None = None):
        self.db_path = db_path
        self.bridge = bridge or OSBridge()
        self.browser = make_browser_controller(bridge)

    async def run(self, request: str) -> str:
        if action_permission("browse_web") != "allow":
            return "I need your confirmation before browsing."
        await self._record_skill(request)
        intent = parse_browser_intent(request)
        if intent.action == "open":
            return await self._open_browser()
        if intent.action == "url":
            return await self._open_url(intent.target)
        if intent.action == "image_search":
            return await self._image_search(intent.target)
        if intent.action == "search":
            return await self._search(intent.target)
        if intent.action == "inspect":
            return await self._inspect()
        if intent.action == "click":
            return await self._click(intent.target)
        if intent.action == "fill":
            return await self._fill(intent.target, intent.value)
        return await self._inspect()

    async def _open_browser(self) -> str:
        await asyncio.to_thread(self.browser.open_new_tab_url, GOOGLE_HOME)
        await upsert_preference(self.db_path, "maya_active_workflow", "browser:open", source="skill")
        return "Browser skill opened Chrome in a new tab."

    async def _open_url(self, url: str) -> str:
        if _looks_sensitive_url(url):
            return "I will not open a URL that looks like login, payment, checkout, OTP, card, or private-key handling."
        await asyncio.to_thread(self.browser.open_new_tab_url, url)
        await upsert_preference(self.db_path, "maya_active_workflow", f"browser:url:{url}", source="skill")
        return f"Browser skill opened this URL in Chrome: {url}"

    async def _search(self, query: str) -> str:
        if not query:
            return "What should I search for?"
        note_browser_intent({"query": query})
        await asyncio.to_thread(self.browser.open_search_new_tab, query)
        await upsert_preference(self.db_path, "maya_active_workflow", f"browser:search:{query}", source="skill")
        return f"Browser skill opened a Google search for: {query}"

    async def _image_search(self, query: str) -> str:
        if not query:
            return "What image topic should I search for?"
        note_browser_intent({"image_query": query})
        url = "https://www.google.com/search?udm=2&q=" + quote_plus(query)
        await asyncio.to_thread(self.browser.open_new_tab_url, url)
        await asyncio.to_thread(time.sleep, 1.5)
        page, options = await self._inspect_image_results()
        await upsert_preference(self.db_path, "maya_active_workflow", f"browser:image_search:{query}", source="skill")
        lines = [f"Browser skill opened Google Images for: {query}", f"url: {page.url or url}"]
        if options:
            lines.append("visible image results:")
            lines.extend(f"{idx}) {item}" for idx, item in enumerate(options[:5], 1))
        else:
            lines.append(
                "visible image results: none readable from the page text yet. "
                "The images may be visible on screen, but I could not extract their titles or sources."
            )
        return "\n".join(lines)

    async def _inspect_image_results(self) -> tuple[BrowserPage, list[str]]:
        try:
            page = await asyncio.to_thread(self.browser.inspect_page, 9000)
        except Exception:
            page = BrowserPage("", "", "")
        try:
            raw = await asyncio.to_thread(self.browser.inspect_search_results, 8)
        except Exception:
            raw = []
        options = [item for item in raw if len(item) >= 12]
        if not options:
            options = _extract_visible_options(page.text)
        return page, options

    async def _inspect(self) -> str:
        try:
            page, elements = await asyncio.gather(
                asyncio.to_thread(self.browser.inspect_page),
                asyncio.to_thread(self.browser.inspect_elements),
            )
        except Exception as exc:
            return f"I could not inspect Chrome yet: {exc}"
        return "Browser skill inspected Chrome.\n" + page_summary(page) + "\n" + element_summary(elements)

    async def _click(self, target: str) -> str:
        if not target:
            return "Which visible browser item should I click?"
        if _sensitive_action_text(target):
            return f"This looks sensitive. I will stop before clicking `{target}`."
        guard = await self._injected_page_guard("click")
        if guard:
            return guard
        try:
            result = await asyncio.to_thread(self.browser.click_text_verified, target)
        except Exception as exc:
            return f"I could not click in Chrome yet: {exc}"
        if not result.clicked:
            return f"I could not find `{target}` as a visible clickable item in Chrome."
        await upsert_preference(self.db_path, "maya_active_workflow", f"browser:clicked:{target}", source="skill")
        verified = "verified a page change" if result.verified else "clicked it, but could not verify a visible change"
        return f"Browser skill clicked `{target}` and {verified}."

    async def _fill(self, target: str, value: str) -> str:
        if not target or not value:
            return "Tell me the field and value to fill."
        if contains_sensitive_info(value) or _sensitive_action_text(f"{target} {value}"):
            return hard_no_private_exposure_text()
        guard = await self._injected_page_guard("fill a field")
        if guard:
            return guard
        try:
            result = await asyncio.to_thread(self.browser.fill_field, target, value)
        except Exception as exc:
            return f"I could not fill that field in Chrome yet: {exc}"
        if not result.startswith("FILLED:"):
            return f"I could not find a visible non-sensitive field matching `{target}` in Chrome."
        await upsert_preference(self.db_path, "maya_active_workflow", f"browser:filled:{target}", source="skill")
        return f"Browser skill filled `{target}` in Chrome and left the page open for you to check."

    async def _record_skill(self, request: str) -> None:
        await init_skill_db(self.db_path)
        scaffold = Path(__file__).resolve().parent / "maya_skills" / "active" / "browser_control.md"
        await upsert_skill(
            self.db_path,
            skill_id=SKILL_ID,
            name=SKILL_NAME,
            description="Open Chrome, search Google, search Google Images, inspect pages, click visible safe items, and fill non-sensitive fields.",
            safety="bounded",
            approval_mode="policy_guard",
            status="active",
            source="local",
            scaffold_path=str(scaffold),
        )
        await record_skill_usage(
            self.db_path,
            skill_id=SKILL_ID,
            name=SKILL_NAME,
            query=request,
            lane="iMac browser_skill",
            reason="browser intent routed to executable local skill",
        )

    async def _injected_page_guard(self, action: str) -> str:
        try:
            page = await asyncio.to_thread(self.browser.inspect_page, 4000)
        except Exception:
            return ""
        return injected_page_action_notice(page, action)


async def run_browser_skill(db_path: str, request: str, *, bridge: OSBridge | None = None) -> str:
    return await BrowserSkill(db_path, bridge).run(request)


def parse_browser_intent(text: str) -> BrowserSkillIntent:
    cleaned = " ".join(text.strip().split())
    lowered = cleaned.lower()
    url = _extract_url(cleaned)
    if url and any(word in lowered for word in ("open", "go to", "visit")):
        return BrowserSkillIntent("url", _normalize_url(url))
    fill = re.match(r"^(?:fill|enter|type)\s+(.+?)\s+(?:with|as|into)\s+(.+)$", cleaned, re.I)
    if fill:
        return BrowserSkillIntent("fill", fill.group(1).strip(), fill.group(2).strip())
    click = re.match(r"^(?:click|choose|select|press)\s+(.+?)(?:\s+(?:in|on)\s+(?:chrome|browser))?$", cleaned, re.I)
    if click:
        return BrowserSkillIntent("click", click.group(1).strip())
    if any(phrase in lowered for phrase in ("inspect browser", "read browser", "what is on chrome", "what is in chrome", "summarize this page", "summarise this page")):
        return BrowserSkillIntent("inspect")
    image_query = _image_query(cleaned)
    if image_query is not None:
        return BrowserSkillIntent("image_search", image_query)
    search_query = _search_query(cleaned)
    if search_query is not None:
        return BrowserSkillIntent("search", search_query)
    if any(phrase in lowered for phrase in ("open browser", "open chrome", "show browser", "show chrome")):
        return BrowserSkillIntent("open")
    return BrowserSkillIntent("inspect")


def _image_query(text: str) -> str | None:
    patterns = (
        r"\b(?:google\s+images?|image\s+search|search\s+images?|find\s+images?|look\s+for\s+images?)\s+(?:for|of|about)?\s*(.+)$",
        r"\b(?:find|search|google)\s+(.+?)\s+(?:on|in)\s+google\s+images?\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return _clean_query(match.group(1))
    return None


def _search_query(text: str) -> str | None:
    patterns = (
        r"^(?:google|search|search\s+for|look\s+up|find\s+online|check\s+online)\s+(.+)$",
        r"^(?:open\s+a\s+search\s+for|open\s+google\s+search\s+for)\s+(.+)$",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return _clean_query(match.group(1))
    return None


def _clean_query(text: str) -> str:
    cleaned = re.sub(r"\b(?:please|for me|maya)\b", " ", text, flags=re.I)
    wrappers = (
        r"^(?:and\s+)?(?:search\s+for|search|find\s+images?\s+(?:for|of)?|find|look\s+for|look\s+up|google)\s+",
        r"^(?:and\s+)?(?:show\s+me|open)\s+",
        r"^(?:and\s+)?(?:images?\s+(?:for|of|about)\s+)",
    )
    previous = ""
    while previous != cleaned:
        previous = cleaned
        for wrapper in wrappers:
            cleaned = re.sub(wrapper, "", cleaned, flags=re.I).strip()
    return " ".join(cleaned.strip(" .").split())


def _extract_url(text: str) -> str:
    match = re.search(r"\bhttps?://[^\s]+|\b(?:www\.)[^\s]+", text, re.I)
    return match.group(0).strip(" .") if match else ""


def _normalize_url(url: str) -> str:
    return url if re.match(r"https?://", url, re.I) else f"https://{url}"


def _looks_sensitive_url(url: str) -> bool:
    return _sensitive_action_text(url)


def _sensitive_action_text(text: str) -> bool:
    lowered = text.lower()
    blocked = (
        "pay",
        "payment",
        "checkout",
        "purchase",
        "passport",
        "card",
        "otp",
        "2fa",
        "password",
        "login",
        "private key",
        "seed phrase",
        "submit booking",
        "confirm booking",
    )
    return any(word in lowered for word in blocked)
