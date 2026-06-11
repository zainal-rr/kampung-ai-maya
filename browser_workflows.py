from __future__ import annotations

import asyncio
import re

from browser_agent_state import BrowserAgentState, observation_id, task_type_for
from browser_control import element_summary, page_summary
from browser_driver import make_browser_controller
from browser_cost_policy import escalation_decision, local_decision
from browser_followup_policy import looks_like_general_question, looks_like_writing_or_advice_request
from browser_untrusted_guard import injected_page_action_notice
from permission_policy import action_permission, contains_sensitive_info, hard_no_private_exposure_text, safe_sensitive_guidance
from screen_service import MacScreenService
from storage import delete_preference, get_preference, upsert_preference
from utils import OSBridge


STATE_KEY = "maya_browser_workflow"
PENDING_CLICK_KEY = "maya_pending_browser_click"
SENSITIVE_WORDS = (
    "buy", "book", "pay", "checkout", "purchase", "submit", "passport",
    "card", "confirm", "login", "password", "otp", "2fa", "upload", "send",
    "private account", "change account",
)
MISSING_SKILL_WORDS = ("hotel", "calendar", "shopping", "shop", "account", "design review", "security review")


class HumanBrowserWorkflowRouter:
    def __init__(self, db_path: str, bridge: OSBridge | None = None, screen=None):
        self.db_path = db_path
        self.bridge = bridge or OSBridge()
        self._browser = None
        self.screen = screen or MacScreenService()

    @property
    def browser(self):
        if self._browser is None:
            self._browser = make_browser_controller(self.bridge)
        return self._browser

    async def handle(self, text: str, channel: str) -> str | None:
        return (
            await self._start(text, channel)
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

    async def _start(self, text: str, channel: str) -> str | None:
        if not _is_browser_start(text):
            return None
        task_type = task_type_for(text)
        state = BrowserAgentState(text.strip(), text.strip(), task_type, steps=[])
        if action_permission("travel_search" if task_type == "flight_search" else "browse_web") != "allow":
            return "I need your confirmation before browsing for that."
        if channel == "telegram":
            state.steps.append("queued browser search from Telegram")
            await self._save(state)
            if task_type == "flight_search":
                return "I queued the flight search. I can compare options on the iMac browser when it is safe to take over Chrome, and I will stop before booking or payment."
            return "I queued the browser search. I can open and inspect Chrome when it is safe to take over the iMac browser."
        state.steps.append("opened search")
        await asyncio.to_thread(_open_search_new_tab, self.browser, state.query)
        await self._save(state)
        if task_type == "flight_search":
            return "I opened Chrome with flight options. I can compare, change filters, and shortlist, but I will stop before booking or payment."
        return "I opened Chrome for that. I can inspect the page, click visible results, fill simple fields, and verify what changed."

    async def _status(self, text: str) -> str | None:
        if _clean(text) not in {
            "browser status", "what are you browsing", "what is the browser task",
            "what are you comparing", "which page did you use",
        }:
            return None
        task = await self._task()
        if not task:
            return "No active browser task right now."
        return (
            f"Browser task: {task.goal}\n"
            f"Task type: {task.task_type}\n"
            f"Current page: {task.page_title or 'not inspected yet'}\n"
            f"Last query: {task.query}\n"
            f"Estimated browser model cost: ${task.estimated_cost:.3f}\n"
            f"Steps: " + ", ".join(task.steps[-5:])
        )

    async def _inspect(self, text: str) -> str | None:
        lowered = _clean(text)
        active = await self._task()
        markers = (
            "inspect browser", "read browser", "what is in chrome", "what is on chrome",
            "compare results", "compare visible", "compare options", "what are you comparing",
            "which page did you use", "double check browser", "look carefully browser",
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
            active.current_url = page.url
            active.page_title = page.title
            active.last_observation_id = observation_id(page.title, page.url, page.text_hash)
            active.compared_options = _options_from_text(page.text)
            active.confidence = 0.75 if page.text else 0.35
            active.steps.append(f"inspected {page.title}")
        visual = "Screen view is available." if screen.visible else f"Screen view unavailable: {screen.status}"
        cost = _cost_note(lowered, active)
        if active:
            await self._save(active)
        return "I inspected Chrome.\n" + page_summary(page) + "\n" + element_summary(elements) + f"\n{visual}{cost}"

    async def _filter_followup(self, text: str) -> str | None:
        task = await self._task()
        if not task:
            return None
        lowered = _clean(text)
        if looks_like_general_question(lowered):
            return None
        if looks_like_writing_or_advice_request(lowered):
            return None
        if any(word in lowered for word in MISSING_SKILL_WORDS):
            return None
        if safe_sensitive_guidance(lowered):
            return None
        if any(word in lowered for word in SENSITIVE_WORDS):
            return "I can help prepare the next step, but I will stop before booking, payment, submission, or private details."
        filter_patterns = (
            r"\bcheaper\b",
            r"\bearlier\b",
            r"\blater\b",
            r"\bdate\b",
            r"\btomorrow\b",
            r"\bbaggage\b",
            r"\bdirect\b",
            r"\bnonstop\b",
            r"\bfilter\b",
            r"\bsort\b",
        )
        action_patterns = (
            r"^(?:make|find|show|sort|filter|change|set|use|compare)\b",
            r"^(?:earlier|later|cheaper|tomorrow|direct|nonstop)\b",
        )
        if not any(re.search(pattern, lowered) for pattern in filter_patterns):
            return None
        if not any(re.search(pattern, lowered) for pattern in action_patterns):
            return None
        if task.retry_count >= 4:
            return "I have tried a few browser refinements already. Tell me the exact filter or site you want next."
        task.query = f"{task.goal} {text}"
        task.filters.append(text)
        task.retry_count += 1
        task.steps.append(f"searched follow-up: {text}")
        await asyncio.to_thread(_open_search_new_tab, self.browser, task.query)
        await self._save(task)
        return "I updated the browser search and kept the browsing task active."

    async def _fill(self, text: str) -> str | None:
        match = re.match(r"^(?:fill|enter|type)\s+(.+?)\s+(?:with|as|into)\s+(.+)$", text, re.IGNORECASE)
        if not match:
            return None
        target, value = match.group(1).strip(), match.group(2).strip()
        if contains_sensitive_info(value):
            return hard_no_private_exposure_text()
        guard = await self._injected_page_guard("fill a field")
        if guard:
            return guard
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
            await self._set_pending(target)
            return f"This looks sensitive. Say yes if you want me to click `{target}` in Chrome."
        guard = await self._injected_page_guard("click")
        if guard:
            return guard
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
        if result.verified:
            state = "I verified a visible change after the click."
        elif result.clicked:
            state = "I clicked it, but I cannot confirm the result yet."
        else:
            state = "The page stayed on the same visible result."
        suffix = " I will still stop before booking, payment, submission, or private details." if sensitive else ""
        return f"I clicked {target} in Chrome and verified the result. {state}{suffix}"

    async def _task(self) -> BrowserAgentState | None:
        raw = await get_preference(self.db_path, STATE_KEY)
        return BrowserAgentState.from_json(raw) if raw else None

    async def _save(self, task: BrowserAgentState) -> None:
        await upsert_preference(self.db_path, STATE_KEY, task.to_json(), source="workflow")

    async def _add_step(self, step: str) -> None:
        task = await self._task()
        if task:
            task.steps.append(step)
            await self._save(task)

    async def _set_pending(self, target: str) -> None:
        task = await self._task()
        if task:
            task.pending_sensitive_action = target
            await self._save(task)

    async def _injected_page_guard(self, action: str) -> str:
        try:
            page = await asyncio.to_thread(self.browser.inspect_page, 4000)
        except Exception:
            return ""
        return injected_page_action_notice(page, action)


def _is_browser_start(text: str) -> bool:
    lowered = _clean(text)
    if "flight" in lowered and any(word in lowered for word in ("check", "find", "search", "book", "compare")):
        return True
    return bool(re.match(r"^(?:browse|search|look up|google|check online|find online)\s+.+", lowered))


def _open_search_new_tab(browser, query: str) -> None:
    opener = getattr(browser, "open_search_new_tab", None)
    if opener:
        opener(query)
        return
    browser.open_search(query)


def _click_target(text: str) -> str | None:
    match = re.match(r"^(?:click|choose|select|press)\s+(.+)$", " ".join(text.strip().split()), re.IGNORECASE)
    if not match:
        return None
    return re.sub(r"\s+(?:in|on)\s+(?:chrome|browser)$", "", match.group(1), flags=re.IGNORECASE).strip(" .")


def _clean(text: str) -> str:
    return " ".join(text.lower().strip().split())


def _options_from_text(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    markers = ("rm", "$", "flight", "airasia", "malaysia", "price", "option")
    return [line[:160] for line in lines if any(marker in line.lower() for marker in markers)][:8]


def _cost_note(text: str, task: BrowserAgentState | None) -> str:
    if not task:
        return ""
    decision = local_decision()
    if any(word in text for word in ("messy", "visual", "double check", "look carefully", "tiny text")):
        decision = escalation_decision(
            reason=text,
            current_cost=task.estimated_cost,
            confidence=task.confidence,
            careful="double check" in text or "look carefully" in text,
        )
    if decision.lane == "local":
        return "\nCost path: local browser evidence only."
    if decision.needs_confirmation:
        return f"\nCost path: {decision.reason} needs confirmation before spending more."
    task.estimated_cost += decision.estimated_cost
    return f"\nCost path: {decision.reason}, estimated +${decision.estimated_cost:.3f}."
