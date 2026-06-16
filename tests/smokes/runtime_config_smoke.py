from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import os
import tempfile
from pathlib import Path

from maya_core.maya_runtime_config import runtime_config
from maya_voice.voice_device_policy import local_wake_allowed, voice_intent_label
from workspace_paths import maya_workspace_root, project_roots


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _restore(key: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = value


def main() -> None:
    keys = (
        "MAYA_OWNER_NAME",
        "TELEGRAM_ALLOWED_CHAT_IDS",
        "MAYA_WORKSPACE_ROOT",
        "MAYA_PROJECT_ROOTS",
        "MAYA_VOICE_ALLOWED_HEADPHONE_NAMES",
        "MAYA_VOICE_BLOCKED_WAKE_NAMES",
        "MAYA_BROWSER_DRIVER",
    )
    old = {key: os.environ.get(key) for key in keys}
    try:
        with tempfile.TemporaryDirectory(prefix="maya-config-") as tmp:
            root = Path(tmp) / "Maya"
            project = Path(tmp) / "ProjectsExtra"
            os.environ["MAYA_OWNER_NAME"] = "Config Owner"
            os.environ["TELEGRAM_ALLOWED_CHAT_IDS"] = "123,456"
            os.environ["MAYA_WORKSPACE_ROOT"] = str(root)
            os.environ["MAYA_PROJECT_ROOTS"] = str(project)
            os.environ["MAYA_VOICE_ALLOWED_HEADPHONE_NAMES"] = "Test Headset"
            os.environ["MAYA_VOICE_BLOCKED_WAKE_NAMES"] = "Blocked Speaker"
            os.environ["MAYA_BROWSER_DRIVER"] = "extension"

            cfg = runtime_config()
            _require(cfg.owner_name == "Config Owner", "owner name did not load from config")
            _require(cfg.telegram_allowed_chat_ids == ("123", "456"), "Telegram allowlist did not parse")
            _require(maya_workspace_root() == root, "workspace root did not flow through config")
            _require(project.resolve(strict=False) in project_roots(), "project roots did not include configured root")
            _require(local_wake_allowed("Test Headset", ""), "configured headset should allow local wake")
            _require(not local_wake_allowed("Blocked Speaker", ""), "configured blocked device should deny local wake")
            _require(voice_intent_label("Test Headset", "") == "sony_headphone_maya", "voice label changed unexpectedly")
            _require(cfg.browser_driver_default == "extension", "browser driver did not load from config")
    finally:
        for key, value in old.items():
            _restore(key, value)
    print("runtime_config_smoke: ok")


if __name__ == "__main__":
    main()
