from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field

from browser_control import BrowserController, element_summary, page_summary
from permission_policy import action_permission, contains_sensitive_info, hard_no_private_exposure_text
from screen_service import MacScreenService
from storage import delete_preference, get_preference, upsert_preference
from utils import OSBridge


STATE_KEY = "maya_browser_workflow"
PENDING_CLICK_KEY = "maya_pending_browser_click"
SENSITIVE_WORDS = ("buy", "book", "pay", "checkout", "purchase", "submit", "passport", "card", "confirm")
MISSING_SKILL_WORDS = ("hotel", "calendar", "shopping", "shop", "account", "design review", "security review")


@dataclass
class BrowserTask:
    goal: str
    query: str
    kind: str = "web"
    steps: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps({"goal": self.goal, "query": self.query, "kind": self.kind, "steps": self.steps[-8:]})

    @classmethod
    def from_json(cls, raw: str) -> "BrowserTask | None":
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return cls(str(data.get("goal", "")), str(data.get("query", "")), str(data.get("kind", "web")), list(data.get("steps", [])))


class HumanBrowserWorkflowRouter:
    def __init__(self, db_path: str, bridge: OSBridge | None = None, screen=None):
        self.db_path = db_path
        self.bridge = bridge or OSBridge()
        self.browser = BrowserController(self.bridge)
        self.screen = screen or MacScreenService()

    async def handle(self, text: str, channel: str) -> str | None:
        return (
            await self._start(text)
            or await self._status(text)
            or await self._inspect(text)
            or await self._fill(text)
            or await self._click(text)
            or await self._filter_followup(text)
            or await self._stop(text)
        )

    async def handle_confirmation(self, text: str) -> str | None:
        if _clean(text) not in {"yes", "yes do it", "approve", "confirm"}:
            return None
        target = await get_preference(self.db_path, PENDING_CLICK_KEY)
        if not target:
            return None
        await delete_preference(self.db_path, PENDING_CLICK_KEY)
        return await self._click_target(target, sensitive=True)

    async def _start(self, text: str) -> str | None:
        if not _is_browser_start(text):
            return None
        kind = "flight" if "flight" in text.lower() else "web"
        task = BrowserTask(text.strip(), text.strip(), kind, ["opened search"])
        if action_permission("travel_search" if kind == "flight" else "browse_web") != "allow":
            return "I need your confirmation before browsing for that."
        await asyncio.to_thread(self.browser.open_search, task.query)
        await self._save(task)
        if kind == "flight":
            return "I opened Chrome with flight options. I can compare, change filters, and shortlist, but I will stop before booking or payment."
        return "I opened Chrome for that. I can inspect the page, click visible results, fill simple fields, and verify what changed."

    async def _status(self, text: str) -> str | None:
        if _clean(text) not in {"browser status", "what are you browsing", "what is the browser task"}:
            return None
        task = await self._task()
        if not task:
            return "No active browser task right now."
        return f"Browser task: {task.goal}\nLast query: {task.query}\nSteps: " + ", ".join(task.steps[-5:])

    async def _inspect(self, text: str) -> str | None:
        lowered = _clean(text)
        active = await self._task()
        markers = (
            "inspect browser", "read browser", "what is in chrome", "what is on chrome",
            "compare results", "compare visible", "compare options",
        )
        if not active and not any(marker in lowered for marker in markers):
            return None
        if active and not (any(marker in lowered for marker in markers) or lowered in {"what do you see", "what can you see", "compare them"}):
            return None
        try:
            page, elements, screen = await asyncio.gather(
                asyncio.to_thread(self.browser.inspect_page),
                asyncio.to_thread(self.browser.inspect_elements),
                asyncio.to_thread(self.screen.capture_once),
            )
        except Exception as exc:
            return f"I could not inspect Chrome yet: {exc}"
        if active:
            active.steps.append(f"inspected {page.title}")
            await self._save(active)
        visual = "Screen view is available." if screen.visible else f"Screen view unavailable: {screen.status}"
        return "I inspected Chrome.\n" + page_summary(page) + "\n" + element_summary(elements) + f"\n{visual}"

    async def _filter_followup(self, text: str) -> str | None:
        task = await self._task()
        if not task:
            return None
        lowered = _clean(text)
        if any(word in lowered for word in MISSING_SKILL_WORDS):
            return None
        if any(word in lowered for word in SENSITIVE_WORDS):
            return "I can help prepare the next step, but I will stop before booking, payment, submission, or private details."
        filter_words = ("cheaper", "earlier", "later", "date", "tomorrow", "baggage", "direct", "nonstop", "filter", "sort")
        if not any(word in lowered for word in filter_words):
            return None
        task.query = f"{task.goal} {text}"
        task.steps.append(f"searched follow-up: {text}")
        await asyncio.to_thread(self.browser.open_search, task.query)
        await self._save(task)
        return "I updated the browser search and kept the browsing task active."

    async def _fill(self, text: str) -> str | None:
        match = re.match(r"^(?:fill|enter|type)\s+(.+?)\s+(?:with|as|into)\s+(.+)$", text, re.IGNORECASE)
        if not match:
            return None
        target, value = match.group(1).strip(), match.group(2).strip()
        if contains_sensitive_info(value):
            return hard_no_private_exposure_text()
        try:
            result = await asyncio.to_thread(self.browser.fill_field, target, value)
        except Exception as exc:
            return f"I could not fill that field in Chrome yet: {exc}"
        if not result.startswith("FILLED:"):
            return f"I could not find a visible field matching `{target}` in Chrome."
        await self._add_step(f"filled {target}")
        return f"I filled {target} in Chrome and kept the page open for you to check."

    async def _click(self, text: str) -> str | None:
        target = _click_target(text)
        if not target:
            return None
        if any(word in _clean(f"{text} {target}") for word in SENSITIVE_WORDS):
            await upsert_preference(self.db_path, PENDING_CLICK_KEY, target, source="workflow")
            return f"This looks sensitive. Say yes if you want me to click `{target}` in Chrome."
        return await self._click_target(target, sensitive=False)

    async def _stop(self, text: str) -> str | None:
        if _clean(text) not in {"stop browsing", "close browser task", "end browser task"}:
            return None
        await delete_preference(self.db_path, STATE_KEY)
        return "Okay. I closed the active browser task."

    async def _click_target(self, target: str, sensitive: bool) -> str:
        try:
            result = await asyncio.to_thread(self.browser.click_text_verified, target)
        except Exception as exc:
            return f"I could not click in Chrome yet: {exc}"
        if not result.clicked:
            return f"I could not find `{target}` as a visible clickable item in Chrome."
        await self._add_step(f"clicked {target}")
        state = "The page changed after the click." if result.changed else "The page stayed on the same visible result."
        suffix = " I will still stop before booking, payment, submission, or private details." if sensitive else ""
        return f"I clicked {target} in Chrome and verified the result. {state}{suffix}"

    async def _task(self) -> BrowserTask | None:
        raw = await get_preference(self.db_path, STATE_KEY)
        return BrowserTask.from_json(raw) if raw else None

    async def _save(self, task: BrowserTask) -> None:
        await upsert_preference(self.db_path, STATE_KEY, task.to_json(), source="workflow")

    async def _add_step(self, step: str) -> None:
        task = await self._task()
        if task:
            task.steps.append(step)
            await self._save(task)


def _is_browser_start(text: str) -> bool:
    lowered = _clean(text)
    if "flight" in lowered and any(word in lowered for word in ("check", "find", "search", "book", "compare")):
        return True
    return bool(re.match(r"^(?:browse|search|look up|google|check online|find online)\s+.+", lowered))


def _click_target(text: str) -> str | None:
    match = re.match(r"^(?:click|choose|select|press)\s+(.+)$", " ".join(text.strip().split()), re.IGNORECASE)
    if not match:
        return None
    return re.sub(r"\s+(?:in|on)\s+(?:chrome|browser)$", "", match.group(1), flags=re.IGNORECASE).strip(" .")


def _clean(text: str) -> str:
    return " ".join(text.lower().strip().split())
