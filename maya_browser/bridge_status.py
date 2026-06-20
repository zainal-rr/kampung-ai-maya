from __future__ import annotations

import json
import os
import signal
import time
from datetime import datetime
from urllib import error, request


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def query_bridge_status(host: str = "127.0.0.1", port: int | None = None, *, timeout: float = 1.0) -> dict:
    if port is None:
        port = _env_int("MAYA_BROWSER_BRIDGE_HEALTH_PORT", 8976)
    url = f"http://{host}:{port}/status"
    try:
        with request.urlopen(url, timeout=timeout) as response:
            payload = response.read().decode("utf-8", "replace")
    except (OSError, error.URLError, TimeoutError):
        return {}
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def seconds_since_iso(value: str) -> float:
    if not value:
        return float("inf")
    try:
        cleaned = value.removesuffix("Z")
        return max(0.0, time.time() - datetime.fromisoformat(cleaned).timestamp())
    except ValueError:
        return float("inf")


def status_is_stale(status: dict, *, stale_seconds: float) -> bool:
    if not status.get("client_connected"):
        return True
    last_ping = str(status.get("last_ping_ok_at") or "")
    return seconds_since_iso(last_ping) > stale_seconds


def terminate_pid(pid: int, *, grace_seconds: float = 1.5) -> bool:
    if pid <= 0 or pid == os.getpid():
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    deadline = time.time() + max(0.1, grace_seconds)
    while time.time() < deadline:
        if not pid_alive(pid):
            return True
        time.sleep(0.05)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    return not pid_alive(pid)


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
