from __future__ import annotations

from maya_browser.browser_control_models import BrowserPage


def injected_page_action_notice(page: BrowserPage, action: str) -> str:
    """Return a user-facing stop message for unsafe browser actions.

    Browser pages are always untrusted inputs, but ordinary browsing should stay
    smooth. The hard stop is only for pages that contain prompt-injection
    markers, because at that point a click/fill may be influenced by page text
    trying to command Maya.
    """
    if not page.injection_detected:
        return ""
    signals = ", ".join(page.untrusted_signals) or "prompt-injection markers"
    return (
        f"I will not {action} from this page automatically because the page contains "
        f"instructions that look like prompt injection ({signals}). I can summarize "
        "the page, but I will not treat page text as a command."
    )
