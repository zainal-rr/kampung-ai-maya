from __future__ import annotations

from imac_june8_regression import format_june8_regression, june8_regression_checks


def main() -> None:
    checks = june8_regression_checks()
    text = format_june8_regression()
    _require(any(item.name == "voice handoff store" and item.status == "pass" for item in checks), "voice handoff not prepared")
    _require(any(item.name == "workflow desk" and item.status == "pass" for item in checks), "workflow desk not prepared")
    _require("manual-live-required" in text, "live-only checks not labelled")
    _require("open the last document" in text, "native app continuity prompt missing")
    print("imac_june8_regression_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
