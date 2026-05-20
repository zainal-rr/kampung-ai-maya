from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from assistant_skill_commands import handle_skill_lifecycle
from skill_factory import SkillFactory
from skill_learning_store import get_skill_learning_metadata, init_skill_learning_db, record_skill_test
from skill_registry import SkillRegistry
from skill_store import find_skill, init_skill_db, update_skill_status, upsert_skill


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-skill-loop-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_skill_db(db_path)
        await init_skill_learning_db(db_path)
        result = await SkillFactory(db_path).scaffold_skill("hotel booking")
        _write_reviewed_scaffold(Path(result["scaffold_path"]))
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
        await record_skill_test(db_path, result["skill_id"], "manual fail", "failed", "Safety failed.", "safety")
        await update_skill_status(db_path, result["skill_id"], "approved")
        reblocked = await handle_skill_lifecycle(db_path, "activate skill hotel booking")
        _require(reblocked and "safety" in reblocked, "latest failed test did not block activation")
        await upsert_skill(db_path, "fake", "fake", "fake", "safe", "none", "approved", "test")
        no_scaffold = await handle_skill_lifecycle(db_path, "activate skill fake")
        _require(no_scaffold and "activation tests" in no_scaffold, "missing scaffold activation should be blocked")
    print("skill_learning_loop_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _write_reviewed_scaffold(path: Path) -> None:
    path.write_text(
        """# hotel booking

## Trigger Phrases
- trigger: book a hotel after Zainal asks for booking help
- non-trigger: general travel chat without booking intent

## Safety
- hard no: no payment, passport, OTP, or login storage
- confirmation: stop before booking submission

## Outputs
- success: shortlisted hotel options and confirmation question

## Implementation Notes
- happy path: search, compare, ask before booking
- failure path: cancel safely and explain blocker
- rollback: close browser workflow without booking

## Tests
- regression: booking intent pauses before payment
- expected: no sensitive action without approval
""",
        "utf-8",
    )


if __name__ == "__main__":
    asyncio.run(main())
