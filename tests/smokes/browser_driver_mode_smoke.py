from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import os
import json
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from maya_browser.browser_control import BrowserController
from maya_browser.browser_driver import make_browser_controller


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _restore(key: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = value


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _bridge_env(port: int, health_port: int, *, owner_kind: str = "") -> dict[str, str]:
    env = os.environ.copy()
    env["MAYA_BROWSER_BRIDGE_PORT"] = str(port)
    env["MAYA_BROWSER_BRIDGE_HEALTH_PORT"] = str(health_port)
    if owner_kind:
        env["MAYA_BROWSER_BRIDGE_OWNER_KIND"] = owner_kind
    return env


def _start_owner_process(port: int, health_port: int, owner_kind: str, ready_path: Path) -> subprocess.Popen:
    code = """
import os, time
from pathlib import Path
from browser_extension_bridge import ExtensionBridgeServer
server = ExtensionBridgeServer(owner_kind=os.environ["OWNER_KIND"])
server.start()
Path(os.environ["READY_PATH"]).write_text(str(os.getpid()), "utf-8")
time.sleep(60)
"""
    env = _bridge_env(port, health_port)
    env["OWNER_KIND"] = owner_kind
    env["READY_PATH"] = str(ready_path)
    proc = subprocess.Popen([sys.executable, "-c", code], env=env)
    deadline = time.time() + 5
    while time.time() < deadline:
        if ready_path.exists():
            return proc
        if proc.poll() is not None:
            raise AssertionError(f"owner process exited early with {proc.returncode}")
        time.sleep(0.05)
    proc.terminate()
    raise AssertionError("owner process did not start")


def _probe_engine_status(port: int, health_port: int) -> dict:
    code = """
import json
from maya_browser.browser_driver import ensure_engine_bridge_started
print(json.dumps(ensure_engine_bridge_started(), sort_keys=True))
"""
    env = _bridge_env(port, health_port, owner_kind="engine")
    env["MAYA_BROWSER_EXTENSION_WAIT_SECONDS"] = "0"
    result = subprocess.run([sys.executable, "-c", code], env=env, text=True, capture_output=True, timeout=10)
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout or f"probe exited {result.returncode}")
    return json.loads(result.stdout.strip().splitlines()[-1])


def _test_foreign_port_ownership() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-bridge-owner-") as tmp:
        root = Path(tmp)

        engine_port, engine_health = _free_port(), _free_port()
        engine_ready = root / "engine.ready"
        engine_proc = _start_owner_process(engine_port, engine_health, "engine", engine_ready)
        try:
            status = _probe_engine_status(engine_port, engine_health)
            _require(status.get("reason_code") == "bridge_owned_by_other_engine", "peer engine ownership was not reported")
            _require(engine_proc.poll() is None, "peer engine must not be killed")
        finally:
            engine_proc.terminate()
            engine_proc.wait(timeout=5)

        manual_port, manual_health = _free_port(), _free_port()
        manual_ready = root / "manual.ready"
        manual_proc = _start_owner_process(manual_port, manual_health, "manual", manual_ready)
        manual_pid = manual_proc.pid
        try:
            status = _probe_engine_status(manual_port, manual_health)
            _require(status.get("owner_kind") == "engine", "stale manual bridge was not reclaimed")
            deadline = time.time() + 3
            while time.time() < deadline and manual_proc.poll() is None:
                time.sleep(0.05)
            _require(manual_proc.poll() is not None, "stale manual bridge process was not terminated")
            _require(manual_pid != int(status.get("server_pid") or 0), "reclaimed bridge reused stale owner PID")
        finally:
            if manual_proc.poll() is None:
                manual_proc.terminate()
                manual_proc.wait(timeout=5)

        unknown_port, unknown_health = _free_port(), _free_port()
        holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        holder.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        holder.bind(("127.0.0.1", unknown_port))
        holder.listen(1)
        try:
            status = _probe_engine_status(unknown_port, unknown_health)
            _require(status.get("reason_code") == "bridge_port_contended", "unknown owner must be reported as contended")
        finally:
            holder.close()


def main() -> None:
    keys = ("MAYA_BROWSER_DRIVER", "MAYA_BROWSER_EXTENSION_WAIT_SECONDS")
    old = {key: os.environ.get(key) for key in keys}
    try:
        os.environ["MAYA_BROWSER_DRIVER"] = "legacy"
        controller = make_browser_controller()
        _require(isinstance(controller, BrowserController), "legacy mode should return AppleScript controller")

        os.environ["MAYA_BROWSER_DRIVER"] = "extension"
        os.environ["MAYA_BROWSER_EXTENSION_WAIT_SECONDS"] = "0"
        try:
            make_browser_controller()
        except RuntimeError as exc:
            _require("extension is not connected" in str(exc), "strict extension failure message changed")
        else:
            raise AssertionError("strict extension mode silently fell back to AppleScript")

        bridge_controller = make_browser_controller(bridge=object())
        _require(isinstance(bridge_controller, BrowserController), "fake bridge tests should keep legacy controller")

        _test_foreign_port_ownership()
    finally:
        for key, value in old.items():
            _restore(key, value)
    print("browser_driver_mode_smoke: ok")


if __name__ == "__main__":
    main()
