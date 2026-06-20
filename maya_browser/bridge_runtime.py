from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from maya_browser.browser_driver import browser_bridge_preflight, ensure_engine_bridge_started
from maya_core.reliability_incidents import (
    record_browser_bridge_preflight_status,
    safe_resolve_incident,
    safe_resolve_open_incidents,
)


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


class BrowserBridgeMonitor:
    def __init__(self) -> None:
        self.interval_seconds = max(1.0, _float_env("MAYA_BROWSER_BRIDGE_MONITOR_SECONDS", 5.0))
        self.ping_timeout_seconds = max(0.2, _float_env("MAYA_BROWSER_BRIDGE_PING_TIMEOUT_SECONDS", 2.5))
        self.last_status: dict[str, Any] = {}
        self._last_reason = ""
        self._active_incident_id = ""

    async def run(self) -> None:
        logger = logging.getLogger("maya.browser.bridge")
        await warm_browser_bridge_once()
        while True:
            status = await asyncio.to_thread(
                browser_bridge_preflight,
                wait_seconds=0.0,
                ping_timeout=self.ping_timeout_seconds,
            )
            self.last_status = dict(status)
            reason = str(status.get("reason_code") or "")
            if status.get("ready"):
                if self._active_incident_id:
                    await asyncio.to_thread(safe_resolve_incident, self._active_incident_id, recovery_status="recovered")
                    self._active_incident_id = ""
                await asyncio.to_thread(
                    safe_resolve_open_incidents,
                    subsystem="browser_bridge",
                    reason_codes=("bridge_no_client", "bridge_stale_ping", "bridge_preflight_failed"),
                    recovery_status="recovered",
                    source_of_truth_checked=True,
                    source_of_truth_result=reason or "ready",
                    user_visible_message="Browser bridge is ready.",
                )
            else:
                incident = await asyncio.to_thread(record_browser_bridge_preflight_status, status)
                if incident is not None:
                    self._active_incident_id = incident.incident_id
            if reason and reason != self._last_reason:
                logger.info(
                    "browser bridge status: reason=%s connected=%s owner=%s pid=%s",
                    reason,
                    status.get("client_connected"),
                    status.get("owner_kind"),
                    status.get("server_pid"),
                )
                self._last_reason = reason
            await asyncio.sleep(self.interval_seconds)


async def warm_browser_bridge_once() -> dict[str, Any]:
    return await asyncio.to_thread(ensure_engine_bridge_started)
