from __future__ import annotations

import tempfile
from pathlib import Path

from live_reliability_soak import SoakDay, format_soak_status, load_soak, record_soak_day, soak_summary


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-soak-") as tmp:
        path = Path(tmp) / "soak.json"
        for index in range(1, 8):
            record_soak_day(SoakDay(day=f"2026-06-0{index}", notes="clean day"), path)
        rows = load_soak(path)
        summary = soak_summary(rows)
        _require(summary["days_recorded"] == 7, "seven days not recorded")
        _require(summary["seven_day_complete"] is True, "soak not complete")
        _require(summary["clean_soak"] is True, "clean soak failed")
        record_soak_day(SoakDay(day="2026-06-07", browser_failures=1), path)
        dirty = soak_summary(load_soak(path))
        _require(dirty["browser_failures"] == 1 and dirty["clean_soak"] is False, "failure not counted")
        _require("browser_failures: 1" in format_soak_status(load_soak(path)), "failure not rendered")
    print("live_reliability_soak_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
