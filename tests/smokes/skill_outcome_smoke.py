from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import tempfile
from pathlib import Path

from maya_core.skill_outcome_store import recent_skill_outcomes, record_skill_outcome
from maya_core.skill_performance_analyzer import analyze_skill_performance
from maya_core.skill_store import init_skill_db, list_skill_proposals, upsert_skill


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-skill-outcome-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_skill_db(db_path)
        await upsert_skill(db_path, "flight_search", "Flight Search", "Find flights.", "bounded", "policy", "active", "test")
        await record_skill_outcome(
            db_path,
            skill_id="flight_search",
            user_request="find flights to Penang",
            outcome="success",
            channel="telegram",
            selected_lane="Gemini",
        )
        await record_skill_outcome(db_path, skill_id="flight_search", user_request="find cheap flights to Penang", outcome="success")
        outcomes = await recent_skill_outcomes(db_path)
        _require(len([item for item in outcomes if item["outcome"] == "success"]) == 2, "success outcomes not recorded")
        await record_skill_outcome(db_path, skill_id="flight_search", user_request="book flight", outcome="failure", missing_step="booking unavailable")
        await record_skill_outcome(db_path, skill_id="flight_search", user_request="book cheaper flight", outcome="failure", missing_step="booking unavailable")
        proposals = await list_skill_proposals(db_path)
        _require(not any("failed" in item["summary"] for item in proposals), "outcome logging should not create failure proposals directly")
        await record_skill_outcome(db_path, skill_id="flight_search", user_request="wrong airport", outcome="user_corrected", user_correction="Use KUL")
        outcomes = await recent_skill_outcomes(db_path)
        _require(any(item["outcome"] == "user_corrected" for item in outcomes), "correction outcome missing")
        await analyze_skill_performance(db_path)
        proposals = await list_skill_proposals(db_path)
        _require(any("failed" in item["summary"] for item in proposals), "analyzer did not create failure proposal")
        _require(any("correction" in item["summary"] for item in proposals), "analyzer did not create correction proposal")
        _require(any(item["channel"] == "telegram" and item["selected_lane"] == "Gemini" for item in outcomes), "channel or lane missing")
    print("skill_outcome_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
