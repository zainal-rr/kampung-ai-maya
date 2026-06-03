from __future__ import annotations

from browser_field_tests import browser_field_scenarios, format_browser_field_tests


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
