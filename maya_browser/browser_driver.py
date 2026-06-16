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

from maya_browser.browser_control import BrowserController
from browser_extension_bridge import ExtensionBridgeServer, ExtensionBrowserController
from maya_browser.bridge_status import query_bridge_status, seconds_since_iso, status_is_stale, terminate_pid
from maya_runtime_config import runtime_config


_EXTENSION_SERVER: ExtensionBridgeServer | None = None
_EXTENSION_FAILED_AT = 0.0
_EXTENSION_LAST_REASON = ""
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

    if mode in {"extension", "chrome_extension", "extension_strict"}:
        raise RuntimeError(
            "Maya Chrome extension strict mode requested, but the Maya Chrome "
            "extension is not connected to the local bridge"
        )

    return BrowserController(app_name=app_name)


def extension_bridge_status() -> dict[str, object]:
    server = _EXTENSION_SERVER
    if server:
        return server.status()
    live = query_bridge_status(timeout=0.5)
    if live:
        if _EXTENSION_LAST_REASON:
            live = dict(live)
            live["reason_code"] = _EXTENSION_LAST_REASON
        return live
    return {
        "owner_kind": "",
        "server_pid": 0,
        "started": bool(server),
        "running": bool(server and server.is_running),
        "connected": bool(server and server.is_connected),
        "client_connected": False,
        "server_running": False,
        "port": server.port if server else 0,
        "health_port": 0,
        "reason_code": _EXTENSION_LAST_REASON or "not_started",
    }


def ensure_engine_bridge_started() -> dict[str, object]:
    server = _ensure_extension_server(strict=True, owner_kind="engine")
    return server.status() if server else extension_bridge_status()


def browser_bridge_preflight(*, wait_seconds: float = 3.0, ping_timeout: float = 1.0) -> dict[str, object]:
    server = _ensure_extension_server(strict=True, owner_kind="engine")
    if server is None:
        status = extension_bridge_status()
        status["ready"] = False
        return status
    deadline = time.time() + max(0.0, wait_seconds)
    while True:
        if server.is_connected and server.ping_client(timeout=ping_timeout, close_on_failure=False):
            status = server.status()
            status["ready"] = True
            return status
        if time.time() >= deadline:
            if server.is_connected and seconds_since_iso(server.last_client_seen_at) > _extension_stale_seconds():
                server.close_client()
            status = server.status()
            status["ready"] = False
            status["reason_code"] = "browser_bridge_unavailable"
            return status
        time.sleep(0.15)


def _extension_controller() -> ExtensionBrowserController | None:
    global _EXTENSION_SERVER, _EXTENSION_FAILED_AT

    mode = _browser_driver_mode()
    if mode not in {"auto", "extension", "chrome_extension", "extension_strict"}:
        return None

    strict = mode in {"extension", "chrome_extension", "extension_strict"}
    for attempt in range(2):
        server = _ensure_extension_server(strict=strict, owner_kind=_owner_kind())
        if server is None:
            return None

        _wait_for_extension_connection(server)

        if not server.is_connected:
            continue

        controller = ExtensionBrowserController(server)
        if _controller_ping(controller):
            _EXTENSION_FAILED_AT = 0.0
            return controller

        # The extension socket can go stale when Chrome suspends/restarts its
        # service worker. Drop the zombie client and wait once for the worker
        # to reconnect to the still-running local bridge.
        server.close_client()
        if attempt == 0:
            _wait_for_extension_connection(server)

    return None


def _ensure_extension_server(*, strict: bool, owner_kind: str | None = None) -> ExtensionBridgeServer | None:
    global _EXTENSION_SERVER, _EXTENSION_FAILED_AT, _EXTENSION_LAST_REASON

    if _EXTENSION_SERVER is not None and not _EXTENSION_SERVER.is_running:
        _EXTENSION_SERVER = None

    if _EXTENSION_SERVER is None:
        # Avoid hammering the port on every browser skill call if startup fails.
        if not strict and _EXTENSION_FAILED_AT and time.time() - _EXTENSION_FAILED_AT < 30:
            return None
        server = _start_extension_server_with_retry(_extension_wait_seconds(), owner_kind=owner_kind or _owner_kind())
        if server is None:
            _EXTENSION_FAILED_AT = time.time()
            return None
        _EXTENSION_LAST_REASON = ""
        _EXTENSION_SERVER = server
    return _EXTENSION_SERVER


def _controller_ping(controller: ExtensionBrowserController) -> bool:
    try:
        return controller.ping()
    except Exception:
        return False


def _wait_for_extension_connection(server: ExtensionBridgeServer) -> None:
    wait_seconds = _extension_wait_seconds()
    if wait_seconds <= 0 or server.is_connected:
        return
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if server.is_connected:
            return
        time.sleep(0.1)


def _start_extension_server_with_retry(wait_seconds: float, *, owner_kind: str) -> ExtensionBridgeServer | None:
    global _EXTENSION_LAST_REASON

    deadline = time.time() + max(3.0, min(30.0, wait_seconds))
    while time.time() < deadline:
        try:
            server = ExtensionBridgeServer(owner_kind=owner_kind)
            server.start()
            return server
        except Exception:  # noqa: BLE001 - transient port races are retried.
            if _handle_foreign_owner():
                continue
            time.sleep(0.25)
    return None


def _handle_foreign_owner() -> bool:
    global _EXTENSION_LAST_REASON

    status = query_bridge_status(timeout=0.5)
    if not status:
        if _EXTENSION_LAST_REASON == "reclaimed_stale_bridge":
            time.sleep(0.2)
            return True
        _EXTENSION_LAST_REASON = "bridge_port_contended"
        return False
    owner_kind = str(status.get("owner_kind") or "")
    owner_pid = int(status.get("server_pid") or 0)
    if owner_pid == os.getpid():
        _EXTENSION_LAST_REASON = "bridge_owned_by_same_process_without_handle"
        return False
    if owner_kind == "engine":
        _EXTENSION_LAST_REASON = "bridge_owned_by_other_engine"
        return False
    if owner_kind in {"codex", "manual"} and status_is_stale(status, stale_seconds=_extension_stale_seconds()):
        if terminate_pid(owner_pid):
            _EXTENSION_LAST_REASON = "reclaimed_stale_bridge"
            time.sleep(0.2)
            return True
    _EXTENSION_LAST_REASON = "bridge_port_contended"
    return False


def _extension_wait_seconds() -> float:
    mode = _browser_driver_mode()
    default = (
        _DEFAULT_STRICT_EXTENSION_WAIT_SECONDS
        if mode in {"extension", "chrome_extension", "extension_strict"}
        else _DEFAULT_AUTO_EXTENSION_WAIT_SECONDS
    )
    raw = os.getenv("MAYA_BROWSER_EXTENSION_WAIT_SECONDS", str(default)).strip()
    try:
        return max(0.0, min(30.0, float(raw)))
    except ValueError:
        return default


def _extension_stale_seconds() -> float:
    raw = os.getenv("MAYA_BROWSER_BRIDGE_STALE_SECONDS", "45").strip()
    try:
        return max(5.0, float(raw))
    except ValueError:
        return 45.0


def _owner_kind() -> str:
    return os.getenv("MAYA_BROWSER_BRIDGE_OWNER_KIND", "codex").strip() or "codex"


def _browser_driver_mode() -> str:
    phase_mode = os.getenv("MAYA_BROWSER_MODE", "").strip().lower()
    if phase_mode in {"extension_strict", "strict_extension"}:
        return "extension_strict"
    if phase_mode in {"legacy", "applescript", "apple"}:
        return "legacy"
    driver_mode = os.getenv("MAYA_BROWSER_DRIVER", "").strip().lower()
    if driver_mode:
        return driver_mode
    return runtime_config().browser_driver_default.strip().lower() or "auto"
