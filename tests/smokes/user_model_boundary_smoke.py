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

from user_model_store import add_user_model_item, list_user_model_items


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-user-model-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        ok, _ = await add_user_model_item(
            db_path,
            category="tone",
            content="Prefers concise, natural replies.",
            source="explicit",
            confidence=0.9,
        )
        _require(ok, "safe user model item was blocked")
        skill_ok, _ = await add_user_model_item(
            db_path,
            category="skill_specific_preferences",
            content="Prefer KUL for flight search.",
            source="explicit",
            skill_id="flight_search",
        )
        _require(skill_ok, "skill-specific user model item was blocked")
        blocked, message = await add_user_model_item(
            db_path,
            category="preferences",
            content="My OTP is 123456.",
            source="explicit",
        )
        _require(not blocked and "Blocked" in message, "OTP user model item was not blocked")
        implicit, message = await add_user_model_item(
            db_path,
            category="work_style",
            content="Seems to prefer quiet planning.",
            source="observation",
        )
        _require(not implicit and "confirmation" in message, "implicit observation saved without confirmation")
        private, message = await add_user_model_item(
            db_path,
            category="preferences",
            content="This is marked private by Zainal.",
            source="explicit",
        )
        _require(not private and "Blocked" in message, "private-marked item was not blocked")
        items = await list_user_model_items(db_path)
        _require(len(items) == 2 and all(item["source"] == "explicit" for item in items), "source missing")
        _require(any(float(item["confidence"]) == 0.9 for item in items), "confidence missing")
        skill_items = await list_user_model_items(db_path, skill_id="flight_search")
        _require(len(skill_items) == 1 and skill_items[0]["skill_id"] == "flight_search", "skill user model scope missing")
    print("user_model_boundary_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
