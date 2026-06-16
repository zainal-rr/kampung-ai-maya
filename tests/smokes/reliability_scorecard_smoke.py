from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


from live_reliability_soak import SoakDay
from reliability_scorecard import format_reliability_scorecard, reliability_scorecard


def main() -> None:
    clean_days = [
        SoakDay(
            day=f"2026-06-{index:02d}",
            telegram_replies=10,
            imac_voice_turns=4,
            file_deliveries=2,
            browser_workflows=1,
            memory_ops=3,
            workflow_recoveries=1,
            uptime_minutes=1440,
        )
        for index in range(1, 31)
    ]
    card = reliability_scorecard(clean_days)
    _require(card.status == "30-day-pass", f"unexpected status: {card.status}")
    _require(card.readiness_score >= 95, "clean 30-day score should be high")
    dirty = reliability_scorecard(clean_days[:-1] + [SoakDay(day="2026-06-30", browser_workflows=2, browser_failures=1)])
    _require(dirty.status == "needs-review", "dirty 30-day run should need review")
    text = format_reliability_scorecard(clean_days[:3])
    _require("insufficient-data" in text, "short scorecard should not overclaim")
    print("reliability_scorecard_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
