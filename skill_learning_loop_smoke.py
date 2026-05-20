from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from assistant_skill_commands import handle_skill_lifecycle
from skill_factory import SkillFactory
from skill_registry import SkillRegistry
from skill_store import find_skill, init_skill_db
from skill_learning_store import get_skill_learning_metadata, init_skill_learning_db


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-skill-loop-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_skill_db(db_path)
        await init_skill_learning_db(db_path)
        result = await SkillFactory(db_path).scaffold_skill("hotel booking")
        skill = await find_skill(db_path, "hotel booking")
        _require(skill and skill["status"] == "proposed", "skill not proposed")
        approved = await handle_skill_lifecycle(db_path, "approve skill hotel booking")
        _require(approved and "approved" in approved, "skill approval failed")
        blocked = await handle_skill_lifecycle(db_path, "activate skill hotel booking")
        _require(blocked and "activation test" in blocked, "untested skill activated")
        tested = await handle_skill_lifecycle(db_path, f"test skill {result['skill_id']}")
        _require(tested and "recorded" in tested, "skill test not recorded")
        active = await handle_skill_lifecycle(db_path, "activate skill hotel booking")
        _require(active and "active" in active, "tested skill not activated")
        await SkillRegistry(db_path).build_prompt_context("hotel booking")
        metadata = await get_skill_learning_metadata(db_path, result["skill_id"])
        _require(metadata and int(metadata["usage_count"]) >= 1, "skill usage metadata not updated")
    print("skill_learning_loop_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
