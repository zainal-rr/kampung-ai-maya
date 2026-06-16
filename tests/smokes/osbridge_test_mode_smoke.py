from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import subprocess
import sys

from utils import OSBridge, _test_mode


class GuardedBridge(OSBridge):
    def __init__(self) -> None:
        self.applescript_calls = 0
        self.subprocess_calls = 0

    def _run_applescript(self, script: str) -> str:
        self.applescript_calls += 1
        raise AssertionError(f"OSBridge attempted AppleScript in smoke mode: {script[:120]}")

    def open_file(self, path: str, app_name: str | None = None):
        if _test_mode():
            return
        self.subprocess_calls += 1
        raise AssertionError(f"OSBridge attempted native open in smoke mode: {path}")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    _require(_test_mode(), "smoke entrypoint should force OSBridge test mode")
    bridge = GuardedBridge()
    bridge.switch_app("Microsoft Word")
    bridge.open_url("https://example.com")
    bridge.open_url_new_tab("https://example.com")
    bridge.open_file("/tmp/maya-test.docx", "Microsoft Word")
    bridge.press_shortcut("option+space")
    bridge.type_text("should not type")
    bridge.notify("Kampung AI", "should not notify")
    _require(bridge.get_frontmost_app() == "Test Mode", "frontmost app should be mocked")
    _require(bridge.list_running_apps() == [], "running apps should be mocked")
    _require(bridge.applescript_calls == 0, "AppleScript should not be called")
    _require(bridge.subprocess_calls == 0, "native open should not be called")

    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from local_ci import _command_check; r=_command_check('env', ('-c', 'import os; print(os.getenv(\"MAYA_TEST_MODE\"))')); print(r.output)",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    _require(proc.stdout.strip().endswith("1"), f"local_ci did not force MAYA_TEST_MODE=1: {proc.stdout!r}")
    print("osbridge_test_mode_smoke: ok")


if __name__ == "__main__":
    main()
