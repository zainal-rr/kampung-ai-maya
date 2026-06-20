from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import inspect
import os
import tempfile
from pathlib import Path

import maya_core.service_install as service_install
import maya_telegram.telegram_bridge as telegram_bridge
from maya_core.permission_policy import path_needs_confirmation
from maya_telegram.telegram_delivery import split_file_markers


def main() -> None:
    _file_marker_checks()
    _path_gate_checks()
    _launch_agent_checks()
    _telegram_bridge_checks()
    print("security_smoke: ok")


def _file_marker_checks() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-security-blocked-") as tmp:
        blocked = Path(tmp) / "secret.env"
        blocked.write_text("TOKEN=abc", encoding="utf-8")
        clean, files = split_file_markers(f"send this\n[file:{blocked}]")
        _require(clean == "send this", "file marker should be removed from visible text")
        _require(files == [], "unapproved absolute file marker should not be sendable")

    with tempfile.TemporaryDirectory(prefix="maya-security-allowed-") as tmp:
        os.environ["MAYA_WORKSPACE_ROOT"] = str(Path(tmp) / "Maya")
        allowed_root = Path(os.environ["MAYA_WORKSPACE_ROOT"])
        allowed_root.mkdir(parents=True, exist_ok=True)
        allowed = allowed_root / "security-smoke.txt"
        allowed.write_text("safe generated artifact", encoding="utf-8")
        _, files = split_file_markers(f"[file:{allowed}]")
        _require(files == [allowed.resolve()], "approved generated artifact should be sendable")


def _path_gate_checks() -> None:
    _require(path_needs_confirmation(Path.home() / ".ssh" / "config"), "SSH writes should be confirmation-gated")
    _require(
        path_needs_confirmation(Path.home() / "Library" / "LaunchAgents" / "x.plist"),
        "launch agent writes should be confirmation-gated",
    )


def _launch_agent_checks() -> None:
    plist = service_install.build_plist()
    args = plist["ProgramArguments"]
    joined = " ".join(args)
    _require("/bin/zsh" not in args, "LaunchAgent should not run through zsh")
    _require("source .env" not in joined, "LaunchAgent should not shell-source .env")


def _telegram_bridge_checks() -> None:
    source = inspect.getsource(telegram_bridge)
    _require("token[:10]" not in source, "Telegram bridge should not print token prefix")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
