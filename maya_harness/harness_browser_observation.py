from __future__ import annotations

from maya_browser.browser_control import element_summary, page_summary
from maya_browser.browser_driver import make_browser_controller
from harness_models import GroundedObservation
from screen_service import MacScreenService
from utils import OSBridge


def browser_observation(max_chars: int = 1800, max_lines: int = 6, max_targets: int = 8) -> GroundedObservation | None:
    try:
        controller = make_browser_controller()
        page = controller.inspect_page(max_chars=max_chars)
        elements = controller.inspect_elements(max_items=12)
    except Exception as exc:
        return GroundedObservation(
            source="browser",
            screenshot_status=f"browser unavailable: {exc}",
            confidence=0.2,
            provenance=("browser_control",),
        )
    try:
        bridge = OSBridge()
        frontmost = bridge.get_frontmost_app()
        running = tuple(bridge.list_running_apps())
    except Exception:
        frontmost, running = "", ()
    screen = MacScreenService().capture_once()
    clickable = tuple(f"{item.kind}: {item.label}" for item in elements if item.kind not in {"input", "textarea", "select"})
    fillable = tuple(f"{item.kind}: {item.label}" for item in elements if item.kind in {"input", "textarea", "select"})
    return GroundedObservation(
        source="browser",
        frontmost_app=frontmost,
        running_apps=running,
        page_title=page.title,
        url=page.url,
        text_summary=page_summary(page, max_lines=max_lines),
        text_hash=page.text_hash,
        modal_state=page.modal_state,
        clickable_targets=clickable[:max_targets],
        fillable_targets=fillable[:max_targets],
        screenshot_status=screen.status if screen.visible else f"unavailable: {screen.status}",
        screen_summary=element_summary(elements, max_items=max_targets),
        confidence=0.75,
        provenance=("browser_dom", "browser_visible_text", "macos_app_state", "screen_capture"),
        untrusted_influence=page.untrusted_influence,
        injection_detected=page.injection_detected,
        untrusted_source=page.untrusted_source,
        untrusted_signals=page.untrusted_signals,
    )


def agentic_browser_message(observation: GroundedObservation, fallback: str = "") -> str:
    lines = ["Browser observation for the workflow:"]
    if observation.text_summary:
        lines.append(observation.text_summary)
    elif observation.page_title or observation.url:
        lines.append(f"Title: {observation.page_title}\nURL: {observation.url}")
    elif fallback:
        lines.append(fallback)
    if observation.clickable_targets:
        lines.append("Visible clickable targets:\n" + "\n".join(observation.clickable_targets[:12]))
    if observation.fillable_targets:
        lines.append("Visible fillable targets:\n" + "\n".join(observation.fillable_targets[:8]))
    if observation.screenshot_status:
        lines.append(f"Screen status: {observation.screenshot_status}")
    return "\n".join(line for line in lines if line)
