from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from maya_browser.browser_driver import browser_bridge_preflight, ensure_engine_bridge_started


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
