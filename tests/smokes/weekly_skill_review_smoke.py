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

from maya_core.skill_outcome_store import record_skill_outcome
from maya_core.skill_store import init_skill_db, upsert_skill
from maya_core.weekly_skill_review import WeeklySkillReviewer, latest_skill_review


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-weekly-skill-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_skill_db(db_path)
        await upsert_skill(db_path, "flight_search", "Flight Search", "Find flights.", "bounded", "policy", "active", "test")
        await record_skill_outcome(db_path, skill_id="flight_search", user_request="flight to Penang", outcome="failure")
        report = await WeeklySkillReviewer(db_path).run(save=True)
        _require("Weekly skill review dry run" in report.summary, "summary missing")
        _require("Recent failures: 1" in report.summary, "failure count missing")
        _require("Stale or unused active skills sampled" in report.summary, "stale skill inspection missing")
        _require("Unsupported-action candidates sampled" in report.summary, "unsupported candidate inspection missing")
        _require("Skills with missing steps" in report.summary, "missing-step section missing")
        saved = await latest_skill_review(db_path)
        _require(saved and "Provider calls used: none" in saved, "review was not saved")
        _require("No skills were edited" in saved, "review should not mutate skills")
    print("weekly_skill_review_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
