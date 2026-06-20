from __future__ import annotations

import asyncio
import os

from maya_browser.browser_driver import extension_bridge_status
from maya_browser.browser_driver import browser_bridge_preflight
from maya_browser.browser_capability import run_browser_capability
from maya_voice.verified_facts import browser_fact, facts_block, work_fact


def _run_browser_capability_sync(db_path: str, request: str) -> str:
    return asyncio.run(run_browser_capability(db_path, request))


async def run_browser_capability_isolated(db_path: str, request: str, *, timeout: float) -> str:
    """Run browser work away from the realtime voice loop.

    Browser controller setup talks to Chrome/the extension and can block in
    synchronous APIs. Keeping it in a worker thread lets stop triggers and voice
    timeouts continue to run even if Chrome does not answer.
    """
    return await asyncio.wait_for(
        asyncio.to_thread(_run_browser_capability_sync, db_path, request),
        timeout=timeout,
    )


async def browser_bridge_preflight_isolated(*, wait_seconds: float, ping_timeout: float) -> dict[str, object]:
    return await asyncio.to_thread(
        browser_bridge_preflight,
        wait_seconds=wait_seconds,
        ping_timeout=ping_timeout,
    )


def strict_browser_mode() -> bool:
    return os.getenv("MAYA_BROWSER_MODE", "extension_strict").strip().lower() in {
        "",
        "extension_strict",
        "strict_extension",
    }


def browser_preflight_seconds() -> float:
    return float(os.getenv("MAYA_VOICE_BROWSER_PREFLIGHT_SECONDS", "12"))


def browser_ping_timeout_seconds() -> float:
    return float(os.getenv("MAYA_BROWSER_BRIDGE_PING_TIMEOUT_SECONDS", "2.5"))


def browser_timeout_seconds() -> float:
    return float(os.getenv("XAI_VOICE_BROWSER_TOOL_TIMEOUT_SECONDS", "45"))


def failed_browser_facts(status: dict, *, work_id: str | None, reason_code: str = "") -> str:
    if not status:
        status = extension_bridge_status()
    return facts_block([
        browser_fact(
            bridge_connected=bool(status.get("client_connected")),
            opened_in_maya_group=False,
            reason_code=reason_code or str(status.get("reason_code") or ""),
            server_pid=status.get("server_pid", ""),
        ),
        work_fact(work_active=False, phase="failed", work_id=work_id or ""),
    ])


def completed_browser_facts(*, last_open: dict, status: str, work_id: str | None) -> str:
    bridge_status = extension_bridge_status()
    return facts_block([
        browser_fact(
            bridge_connected=bool(bridge_status.get("client_connected")),
            opened_in_maya_group=bool(last_open.get("openedInMayaGroup")),
            window_id=last_open.get("windowId", ""),
            group_id=last_open.get("groupId", ""),
            tab_id=last_open.get("tabId", ""),
            url=str(last_open.get("url") or ""),
            title=str(last_open.get("title") or ""),
            reason_code=str(bridge_status.get("reason_code") or ""),
            server_pid=bridge_status.get("server_pid", ""),
        ),
        work_fact(work_active=False, phase="done" if status == "completed" else "failed", work_id=work_id or ""),
    ])
