from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import aiosqlite

from harness_graph import HarnessGraphRunner
from harness_state import initial_harness_state
from harness_store import init_harness_db
from skill_learning_store import init_skill_learning_db
from skill_store import init_skill_db
from storage import init_db


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-skill-replay-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        os.environ["MAYA_SKILL_DIR"] = str(Path(tmp) / "maya_skills")
        await init_db(db_path)
        await init_harness_db(db_path)
        await init_skill_db(db_path)
        await init_skill_learning_db(db_path)
        state = initial_harness_state(
            run_id="skill_replay",
            thread_id="harness:skill_replay",
            channel="telegram",
            user_text="hotel booking",
            workflow_type="skill",
        )
        state["approval_result"] = "approved"
        state["user_turn_id"] = "skill_replay:turn"
        await HarnessGraphRunner(db_path).run(state)
        await HarnessGraphRunner(db_path).run(dict(state))
        proposals = await _count(db_path, "skill_proposals")
        skills = await _count(db_path, "skills")
        _require(proposals == 1, f"duplicate skill proposals: {proposals}")
        _require(skills == 1, f"duplicate skill rows: {skills}")
    print("harness_skill_replay_smoke: ok")


async def _count(db_path: str, table: str) -> int:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(f"SELECT COUNT(*) FROM {table}")
        row = await cursor.fetchone()
    return int(row[0])


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
