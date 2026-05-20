from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from skill_registry import SkillRegistry
from skill_store import init_skill_db, latest_skill_usage, upsert_skill


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
