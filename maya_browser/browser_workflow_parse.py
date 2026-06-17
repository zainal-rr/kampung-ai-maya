from __future__ import annotations

import re

from maya_browser.browser_agent_state import BrowserAgentState
from maya_browser.browser_workflow_helpers import is_url


def clean_browser_text(text: str) -> str:
    return " ".join(text.lower().strip().split())


def browser_start_requested(text: str) -> bool:
    lowered = clean_browser_text(text)
    if is_url(lowered):
        return True
    if "flight" in lowered and any(word in lowered for word in ("check", "find", "search", "book", "compare")):
        return True
    return bool(re.match(r"^(?:browse|search|look up|google|check online|find online)\s+.+", lowered))


def click_target_from_text(text: str) -> str | None:
    match = re.match(r"^(?:click|choose|select|press)\s+(.+)$", " ".join(text.strip().split()), re.IGNORECASE)
    if not match:
        return None
    return re.sub(r"\s+(?:in|on)\s+(?:chrome|browser)$", "", match.group(1), flags=re.IGNORECASE).strip(" .")


def browser_state_payload(task: BrowserAgentState | None) -> dict[str, str]:
    if task is None:
        return {}
    return {
        "current_url": task.current_url,
        "page_title": task.page_title,
        "last_observation_id": task.last_observation_id,
        "task_type": task.task_type,
    }
