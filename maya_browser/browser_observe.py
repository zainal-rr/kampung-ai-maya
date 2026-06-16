from __future__ import annotations

"""Page readiness, blocked-page detection, and screenshot evidence capture.

`wait_for_content` replaces fixed sleeps: it polls the visible page until the
text is long enough and stable across two polls, or reports a blocked page or
timeout honestly instead of letting Maya answer from a half-loaded page.
"""

import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from browser_control import BrowserController, BrowserPage


BLOCKED_MARKERS = (
    "unusual traffic",
    "verify you are human",
    "are you a robot",
    "i'm not a robot",
    "enable javascript",
    "access denied",
    "captcha",
    "pardon our interruption",
    "request blocked",
    "you've been blocked by network security",
    "blocked by network security",
    "our cdn was unable to reach our servers",
)


@dataclass(frozen=True)
class PageReadiness:
    ready: bool
    blocked: bool
    reason: str
    page: BrowserPage


def wait_for_content(
    browser: BrowserController,
    *,
    min_chars: int = 400,
    stable_seconds: float = 1.2,
    timeout_seconds: float = 20.0,
    poll_seconds: float = 1.0,
    require_any: tuple[str, ...] = (),
    max_chars: int = 12000,
    clock=time.monotonic,
    sleep=time.sleep,
) -> PageReadiness:
    deadline = clock() + timeout_seconds
    last_hash = ""
    stable_since: float | None = None
    last_page = BrowserPage("", "", "")
    last_error = ""
    while clock() < deadline:
        try:
            page = browser.inspect_page(max_chars)
        except Exception as exc:  # noqa: BLE001 - browser state is external
            last_error = f"{type(exc).__name__}: {exc}"
            sleep(poll_seconds)
            continue
        last_page = page
        blocked = blocked_marker(page.text)
        if blocked:
            return PageReadiness(False, True, f"blocked: {blocked}", page)
        if _content_ready(page, min_chars, require_any):
            if page.text_hash == last_hash:
                if stable_since is not None and clock() - stable_since >= stable_seconds:
                    return PageReadiness(True, False, "content stable", page)
            else:
                last_hash = page.text_hash
                stable_since = clock()
        sleep(poll_seconds)
    reason = "timeout waiting for content"
    if last_error:
        reason += f"; last error: {last_error}"
    return PageReadiness(False, False, reason, last_page)


def blocked_marker(text: str) -> str:
    lowered = text.lower()
    for marker in BLOCKED_MARKERS:
        if marker in lowered:
            return marker
    return ""


def capture_screenshot(directory: Path, label: str, *, runner=subprocess.run) -> str:
    """Capture the screen with macOS `screencapture`; returns path or ''."""
    if not shutil.which("screencapture"):
        return ""
    directory.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%H%M%S")
    safe_label = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in label)[:60]
    path = directory / f"{safe_label}_{stamp}.png"
    try:
        result = runner(
            ["screencapture", "-x", str(path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:  # noqa: BLE001 - screenshot failure must never break a run
        return ""
    if getattr(result, "returncode", 1) != 0 or not path.exists():
        return ""
    return str(path)


def _content_ready(page: BrowserPage, min_chars: int, require_any: tuple[str, ...]) -> bool:
    if len(page.text) < min_chars:
        return False
    if not require_any:
        return True
    lowered = page.text.lower()
    return any(marker.lower() in lowered for marker in require_any)
