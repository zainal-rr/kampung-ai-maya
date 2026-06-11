from __future__ import annotations

import os

from browser_control import BrowserController
from browser_driver import make_browser_controller


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _restore(key: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = value


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
    finally:
        for key, value in old.items():
            _restore(key, value)
    print("browser_driver_mode_smoke: ok")


if __name__ == "__main__":
    main()
