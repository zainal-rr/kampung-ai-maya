from __future__ import annotations

import re

from browser_agent_state import BrowserAgentState
from browser_control_models import BrowserPage
from browser_cost_policy import escalation_decision, local_decision


def open_browser_target_new_tab(browser, query: str) -> BrowserPage | None:
    if is_url(query):
        browser.open_new_tab_url(query.strip())
        return _inspect_after_open(browser)
    opener = getattr(browser, "open_search_new_tab", None)
    if opener:
        opener(query)
        return _inspect_after_open(browser)
    browser.open_search(query)
    return _inspect_after_open(browser)


def _inspect_after_open(browser) -> BrowserPage | None:
    inspector = getattr(browser, "inspect_page", None)
    if not inspector:
        return None
    try:
        return inspector(max_chars=1200)
    except TypeError:
        try:
            return inspector()
        except Exception:
            return None
    except Exception:
        return None


def click_search_result_candidates(target: str) -> list[str]:
    cleaned = " ".join(target.split()).strip()
    candidates = [cleaned]
    stripped = re.sub(r"\s+(?:search\s+)?result(?:\s+link)?$", "", cleaned, flags=re.IGNORECASE).strip()
    if stripped and stripped not in candidates:
        candidates.append(stripped)
    return candidates


def browser_options_from_text(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    markers = ("rm", "$", "flight", "airasia", "malaysia", "price", "option")
    return [line[:160] for line in lines if any(marker in line.lower() for marker in markers)][:8]


def browser_cost_note(text: str, task: BrowserAgentState | None) -> str:
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


def is_url(text: str) -> bool:
    return bool(re.match(r"^https?://\S+$", text.strip(), re.IGNORECASE))
