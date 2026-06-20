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

from maya_core.skill_registry import SkillRegistry
from maya_core.skill_store import init_skill_db, latest_skill_usage, upsert_skill


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-skill-usage-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_skill_db(db_path)
        registry = SkillRegistry(db_path)

        await upsert_skill(
            db_path,
            skill_id="hotel_booking",
            name="Hotel Booking",
            description="Compare hotels before booking.",
            safety="sensitive",
            approval_mode="chat_confirmation",
            status="proposed",
            source="test",
        )
        proposed = await registry.build_prompt_context("hotel booking")
        _require("Hotel Booking" not in proposed, "proposed skill leaked")

        await upsert_skill(
            db_path,
            skill_id="hotel_booking",
            name="Hotel Booking",
            description="Compare hotels before booking.",
            safety="sensitive",
            approval_mode="chat_confirmation",
            status="active",
            source="test",
        )
        context = await registry.build_prompt_context("hotel booking")
        _require("Hotel Booking" in context, "active skill missing")
        events = await latest_skill_usage(db_path)
        _require(any(item["skill_id"] == "hotel_booking" for item in events), "skill usage not logged")
        print("skill_usage_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
