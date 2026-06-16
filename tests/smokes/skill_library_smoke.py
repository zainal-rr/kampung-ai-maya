from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import os
import tempfile
from pathlib import Path

from maya_core.assistant_skill_commands import handle_skill_lifecycle
from skill_factory import SkillFactory
from skill_learning_store import init_skill_learning_db
from skill_store import find_skill, init_skill_db


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-skill-library-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        os.environ["MAYA_SKILL_DIR"] = str(Path(tmp) / "maya_skills")
        await init_skill_db(db_path)
        await init_skill_learning_db(db_path)
        result = await SkillFactory(db_path).scaffold_skill("hotel booking")
        proposed = Path(result["scaffold_path"])
        _require(proposed.parent.name == "proposed" and proposed.exists(), "scaffold not in proposed library")
        _write_reviewed_scaffold(proposed)
        _require((Path(tmp) / "maya_skills" / "tests" / "hotel_booking.md").exists(), "test spec missing")
        approved = await handle_skill_lifecycle(db_path, "approve skill hotel booking")
        _require(approved and "approved" in approved, "approval failed")
        tested = await handle_skill_lifecycle(db_path, "test skill hotel booking")
        _require(tested and "Skill tests recorded" in tested, "required tests not recorded")
        active = await handle_skill_lifecycle(db_path, "activate skill hotel booking")
        _require(active and "active" in active, "activation failed")
        active_path = Path(tmp) / "maya_skills" / "active" / "hotel_booking.md"
        _require(active_path.exists(), "active mirror missing")
        _require("Active library mirror" in active_path.read_text("utf-8"), "active mirror status wrong")
        disabled = await handle_skill_lifecycle(db_path, "disable skill hotel booking")
        _require(disabled and "disabled" in disabled, "disable failed")
        disabled_path = Path(tmp) / "maya_skills" / "disabled" / "hotel_booking.md"
        _require(disabled_path.exists(), "disabled mirror missing")
        _require("Disabled library mirror" in disabled_path.read_text("utf-8"), "disabled mirror status wrong")
        skill = await find_skill(db_path, "hotel booking")
        _require(skill and skill["status"] == "disabled", "database did not stay source of truth")
    print("skill_library_smoke: ok")


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
