from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


from maya_browser.browser_field_tests import browser_field_scenarios, format_browser_field_tests


def main() -> None:
    scenarios = browser_field_scenarios()
    _require(len(scenarios) >= 7, "browser field scenarios missing")
    _require(all(item.status == "pass" for item in scenarios), "deterministic browser field proof failed")
    text = format_browser_field_tests()
    _require("Find flights to Penang" in text, "flight field test missing")
    _require("Stop before booking" in text, "booking boundary missing")
    _require("Research with citations" in text, "source-aware scenario missing")
    _require("real browser reliability still needs live runs" in text, "live boundary missing")
    print("browser_field_tests_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
