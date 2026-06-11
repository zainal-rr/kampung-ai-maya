from __future__ import annotations

"""Browser driver selection for Maya browser skills.

Production uses the Maya Chrome extension by default, while tests that pass
fake OSBridge instances keep the original AppleScript path. Set
MAYA_BROWSER_DRIVER=legacy only when deliberately using the old AppleScript
fallback.
"""

import os
import time
from typing import Any

from browser_control import BrowserController
from browser_extension_bridge import ExtensionBridgeServer, ExtensionBrowserController
from maya_runtime_config import runtime_config


_EXTENSION_SERVER: ExtensionBridgeServer | None = None
_EXTENSION_FAILED_AT = 0.0
_DEFAULT_AUTO_EXTENSION_WAIT_SECONDS = 4.0
_DEFAULT_STRICT_EXTENSION_WAIT_SECONDS = 30.0


def make_browser_controller(bridge: Any | None = None, app_name: str = "Google Chrome"):
    """Return the best available browser controller.

    If a bridge is supplied, keep the legacy BrowserController path so all
    fake-bridge and AppleScript tests behave exactly as before. Without an
    explicit bridge, the default is strict extension mode: browser proof runs
    cannot silently become AppleScript runs. `MAYA_BROWSER_DRIVER=legacy`
    deliberately opts into the old AppleScript path.
    """
    if bridge is not None:
        return BrowserController(bridge, app_name=app_name)

    mode = _browser_driver_mode()
    if mode in {"applescript", "apple", "legacy"}:
        return BrowserController(app_name=app_name)

    controller = _extension_controller()
    if controller is not None:
        return controller

    if mode in {"extension", "chrome_extension"}:
        raise RuntimeError(
            "MAYA_BROWSER_DRIVER=extension requested, but the Maya Chrome "
            "extension is not connected to the local bridge"
        )

    return BrowserController(app_name=app_name)


def extension_bridge_status() -> dict[str, object]:
    server = _EXTENSION_SERVER
    return {
        "started": bool(server),
        "connected": bool(server and server.is_connected),
        "port": server.port if server else 0,
    }


def _extension_controller() -> ExtensionBrowserController | None:
    global _EXTENSION_SERVER, _EXTENSION_FAILED_AT

    mode = _browser_driver_mode()
    if mode not in {"auto", "extension", "chrome_extension"}:
        return None

    if _EXTENSION_SERVER is None:
        # Avoid hammering the port on every browser skill call if startup fails.
        if _EXTENSION_FAILED_AT and time.time() - _EXTENSION_FAILED_AT < 30:
            return None
        server = _start_extension_server_with_retry(_extension_wait_seconds())
        if server is None:
            _EXTENSION_FAILED_AT = time.time()
            return None
        _EXTENSION_SERVER = server

    _wait_for_extension_connection(_EXTENSION_SERVER)

    if _EXTENSION_SERVER.is_connected:
        return ExtensionBrowserController(_EXTENSION_SERVER)

    return None


def _wait_for_extension_connection(server: ExtensionBridgeServer) -> None:
    wait_seconds = _extension_wait_seconds()
    if wait_seconds <= 0 or server.is_connected:
        return
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if server.is_connected:
            return
        time.sleep(0.1)


def _start_extension_server_with_retry(wait_seconds: float) -> ExtensionBridgeServer | None:
    deadline = time.time() + max(1.0, min(30.0, wait_seconds))
    while time.time() < deadline:
        try:
            server = ExtensionBridgeServer()
            server.start()
            return server
        except Exception:  # noqa: BLE001 - transient port races are retried.
            time.sleep(0.25)
    return None


def _extension_wait_seconds() -> float:
    mode = _browser_driver_mode()
    default = (
        _DEFAULT_STRICT_EXTENSION_WAIT_SECONDS
        if mode in {"extension", "chrome_extension"}
        else _DEFAULT_AUTO_EXTENSION_WAIT_SECONDS
    )
    raw = os.getenv("MAYA_BROWSER_EXTENSION_WAIT_SECONDS", str(default)).strip()
    try:
        return max(0.0, min(30.0, float(raw)))
    except ValueError:
        return default


def _browser_driver_mode() -> str:
    return runtime_config().browser_driver_default.strip().lower() or "auto"
