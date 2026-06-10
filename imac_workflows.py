from __future__ import annotations

import asyncio
import re
from pathlib import Path

from assistant_command_helpers import confirmation_decision
from artifact_builder import ArtifactBuilder
from browser_control import page_summary
from browser_driver import make_browser_controller
from browser_workflows import HumanBrowserWorkflowRouter
from document_actions import DocumentActionRouter
from network_tools import network_doc_sections, run_network_diagnostics, summarize_network
from office_modern_files import create_docx
from permission_policy import action_permission
from storage import delete_preference, get_preference, upsert_preference
from utils import OSBridge
from workspace_paths import workspace_dir

SENSITIVE_BROWSER_WORDS = ("buy", "book", "pay", "checkout", "purchase", "submit", "passport", "card", "confirm")
MISSING_SKILL_WORDS = ("hotel", "calendar", "shopping", "shop", "account", "design review", "security review")


class ImacWorkflowRouter:
    def __init__(self, db_path: str, bridge: OSBridge | None = None, workspace: Path | None = None):
        self.db_path = db_path
        self.bridge = bridge or OSBridge()
        self.browser = make_browser_controller(bridge)
        self.human_browser = HumanBrowserWorkflowRouter(db_path, self.bridge)
        self.workspace = workspace or workspace_dir("")
        self.documents = DocumentActionRouter(db_path, workspace=self.workspace, bridge=self.bridge)

    async def handle(self, text: str, channel: str) -> str | None:
        return (
            await self.human_browser.handle(text, channel)
            or await self._flight_start(text)
            or await self._browser_inspect(text)
            or await self._browser_click(text)
            or await self._flight_followup(text)
            or await self._presentation(text, channel)
            or await self._network_doc(text, channel)
        )

    async def handle_confirmation(self, text: str) -> str | None:
        browser_confirmation = await self.human_browser.handle_confirmation(text)
        if browser_confirmation is not None:
            return browser_confirmation
        decision = confirmation_decision(text)
        if not decision:
            return None
        target = await get_preference(self.db_path, "maya_pending_browser_click")
        if not target:
            return None
        await delete_preference(self.db_path, "maya_pending_browser_click")
        if decision != "approve":
            return "Okay, I will not click that."
        return await self._click_target(target, sensitive=True)

    async def _flight_start(self, text: str) -> str | None:
        lowered = _clean(text)
        if not ("flight" in lowered and any(word in lowered for word in ("check", "find", "search", "book"))):
            return None
        query = re.sub(r"\s+in\s+(?:my\s+)?i?mac$", "", text, flags=re.IGNORECASE).strip()
        await self._open_search(query)
        await upsert_preference(self.db_path, "maya_active_workflow", f"flight:{query}", source="workflow")
        return (
            "I opened Chrome with flight options. Tell me if you want a different date, "
            "cheaper option, better timing, or baggage comparison. I will stop before booking or payment."
        )

    async def _flight_followup(self, text: str) -> str | None:
        active = await get_preference(self.db_path, "maya_active_workflow")
        if not active or not active.startswith("flight:"):
            return None
        lowered = _clean(text)
        if any(word in lowered for word in MISSING_SKILL_WORDS):
            return None
        if any(word in lowered for word in ("buy", "book", "pay", "checkout", "purchase")):
            return (
                "Pick the exact flight first. After that I can help continue to checkout, "
                "but I will ask before booking, payment, or private details."
            )
        if not any(word in lowered for word in ("date", "cheaper", "cheap", "earlier", "later", "baggage", "compare", "option")):
            return None
        base = active.split(":", 1)[1]
        query = f"{base} {text}"
        await self._open_search(query)
        await upsert_preference(self.db_path, "maya_active_workflow", f"flight:{query}", source="workflow")
        return "I updated the flight search in Chrome."

    async def _browser_inspect(self, text: str) -> str | None:
        lowered = _clean(text)
        markers = ("inspect browser", "read browser", "what is in chrome", "what is on chrome", "compare visible", "compare results", "compare flight")
        if not any(marker in lowered for marker in markers):
            return None
        try:
            page = await asyncio.to_thread(self.browser.inspect_page)
        except Exception as exc:
            return f"I could not inspect Chrome yet: {exc}"
        return "I inspected the active Chrome page.\n" + page_summary(page)

    async def _browser_click(self, text: str) -> str | None:
        target = _click_target(text)
        if not target:
            return None
        if _is_sensitive_browser_action(f"{text} {target}"):
            await upsert_preference(self.db_path, "maya_pending_browser_click", target, source="workflow")
            return f"This looks sensitive. Say yes if you want me to click `{target}` in Chrome."
        return await self._click_target(target, sensitive=False)

    async def _click_target(self, target: str, sensitive: bool) -> str:
        try:
            result = await asyncio.to_thread(self.browser.click_text_verified, target)
        except Exception as exc:
            return f"I could not click in Chrome yet: {exc}"
        if result.clicked:
            state = "The page changed after the click." if result.changed else "The page stayed on the same visible result."
            suffix = " I will still stop before booking, payment, or private details." if sensitive else ""
            return f"I clicked {target} in Chrome and verified the result. {state}{suffix}"
        return f"I could not find `{target}` as a visible clickable item in Chrome."

    async def _presentation(self, text: str, channel: str) -> str | None:
        match = re.search(r"(?:make|create|craft)\s+(?:a\s+)?(?:presentation|pptx|slides)\s+(?:on|about)\s+(.+)$", text, re.IGNORECASE)
        if not match:
            return None
        if action_permission("create_presentation") != "allow":
            return "I need your confirmation before creating that presentation."
        topic = match.group(1).strip()
        reply = await self.documents._create_powerpoint(topic, channel)
        await upsert_preference(self.db_path, "maya_active_workflow", "presentation:latest_document", source="workflow")
        return reply

    async def _network_doc(self, text: str, channel: str) -> str | None:
        lowered = _clean(text)
        if not ("network" in lowered and any(word in lowered for word in ("what happened", "troubleshoot", "check", "diagnose"))):
            return None
        if action_permission("network_check") != "allow":
            return "I need your confirmation before checking the network."
        results = await asyncio.to_thread(run_network_diagnostics)
        path = self.workspace / "reports" / "network-troubleshooting.docx"
        sections = network_doc_sections(results)
        await asyncio.to_thread(create_docx, path, "Network Troubleshooting Notes", sections)
        artifact = await ArtifactBuilder(self.db_path, self.bridge).finish_docx(
            path,
            "network troubleshooting notes",
            channel,
            run_id="network_troubleshooting",
            source_tool="imac_workflows",
            success_message=f"{summarize_network(results)} I opened the troubleshooting document in Word: {path}",
            draft_message=(
                f"{summarize_network(results)} I opened the troubleshooting draft in Word, "
                f"but QA found issues. {path}"
            ),
            open_file=True,
        )
        await upsert_preference(self.db_path, "maya_active_workflow", f"network:{path}", source="workflow")
        return artifact.reply

    async def _open_search(self, query: str) -> None:
        await asyncio.to_thread(self.browser.open_search_new_tab, query)


def _clean(text: str) -> str:
    return " ".join(text.lower().strip().split())


def _click_target(text: str) -> str | None:
    cleaned = " ".join(text.strip().split())
    match = re.match(r"^(?:click|choose|select|press)\s+(.+)$", cleaned, re.IGNORECASE)
    if not match:
        match = re.match(r"^open\s+(?:the\s+)?(.+?\s+(?:result|link))$", cleaned, re.IGNORECASE)
    if not match:
        return None
    target = re.sub(r"\s+(?:in|on)\s+(?:chrome|browser)$", "", match.group(1), flags=re.IGNORECASE)
    return target.strip(" .")


def _is_sensitive_browser_action(text: str) -> bool:
    lowered = _clean(text)
    return any(word in lowered for word in SENSITIVE_BROWSER_WORDS)
