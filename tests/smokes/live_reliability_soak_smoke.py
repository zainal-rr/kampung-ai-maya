from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import tempfile
from datetime import date, datetime
from pathlib import Path

from maya_harness.live_reliability_collectors import infer_reliability_counts
from maya_harness.live_reliability_soak import (
    AUTO_RECORD_NOTE,
    SoakDay,
    format_soak_status,
    infer_soak_day,
    load_soak,
    record_soak_day,
    soak_summary,
)


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
        repo_root = Path(tmp) / "repo"
        maya_root = Path(tmp) / "Maya"
        (repo_root / "logs").mkdir(parents=True)
        (maya_root / "voice_sessions").mkdir(parents=True)
        (maya_root / "voice_sessions" / "voice-session-2026-06-17-1-v1.md").write_text(
            "\n".join(
                [
                    "# Maya Voice Session",
                    "## Diagnostics",
                    "- Close reason: manual_stop",
                    "- Audio errors: 0",
                    "## Transcript",
                    "### 2026-06-17 09:02:00 User",
                    "Google",
                    "### 2026-06-17 09:02:01 User",
                    "Google search Langkawi",
                    "### 2026-06-17 09:02:04 Maya",
                    "Let me check Chrome first.",
                    "### 2026-06-17 09:02:05 Tool [run_browser_skill]",
                    'call run_browser_skill args {"request": "Google search Langkawi"}',
                    "### 2026-06-17 09:02:07 Tool [run_browser_skill]",
                    "result Request: Google search Langkawi Status: completed",
                    "### 2026-06-17 09:03:00 User",
                    "Make a spreadsheet",
                    "### 2026-06-17 09:03:01 Tool [start_maya_work]",
                    'call start_maya_work args {"request": "Make a spreadsheet"}',
                    "### 2026-06-17 09:03:04 Tool [start_maya_work]",
                    "result Request: Make a spreadsheet Status: failed",
                    "### 2026-06-17 09:04:00 User",
                    "Google search broken",
                    "### 2026-06-17 09:04:01 Tool [run_browser_skill]",
                    'call run_browser_skill args {"request": "Google search broken"}',
                    "### 2026-06-17 09:04:04 Tool [run_browser_skill]",
                    "result Request: Google search broken Status: failed Result: browser_bridge_unavailable",
                ]
            ),
            "utf-8",
        )
        (repo_root / "logs" / "kampung_ai_controller.log").write_text(
            "\n".join(
                [
                    "2026-06-17 09:00:00 Kampung AI is running...",
                    "2026-06-17 10:30:00 Kampung AI is quitting...",
                ]
            ),
            "utf-8",
        )
        counts = infer_reliability_counts(
            date(2026, 6, 17),
            repo_root=repo_root,
            maya_root=maya_root,
            now=datetime(2026, 6, 17, 11, 0, 0),
        )
        _require(counts.imac_voice_turns == 3, "voice turns not inferred")
        _require(counts.browser_workflows == 2, "browser workflows not inferred")
        _require(counts.file_deliveries == 1, "file deliveries not inferred")
        _require(counts.browser_failures == 1, "browser failures not inferred")
        _require(counts.file_delivery_failures == 1, "file failures not inferred")
        _require(counts.uptime_minutes == 90, "uptime not inferred")
        inferred = infer_soak_day(
            date(2026, 6, 17),
            repo_root=repo_root,
            maya_root=maya_root,
            notes="manual wrong-route review pending",
        )
        _require(inferred.browser_workflows == 2, "auto soak row missed browser workflows")
        _require(AUTO_RECORD_NOTE in inferred.notes, "auto provenance note missing")
    print("live_reliability_soak_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
