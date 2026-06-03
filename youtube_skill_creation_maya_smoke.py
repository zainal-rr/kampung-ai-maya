from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from assistant import KampungAssistant
from context_layers import init_context_layers_db
from lesson_store import init_lesson_db
from routine_store import init_routine_db
from session_memory_store import init_session_memory_db
from skill_store import find_skill, init_skill_db
from storage import init_db
from weekly_memory_store import init_weekly_memory_db
from workflow_store import init_workflow_db


class ExplodingResponder:
    async def chat(self, messages):
        raise AssertionError("provider fallback should not be called")


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-youtube-skill-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        os.environ["MAYA_SKILL_DIR"] = str(Path(tmp) / "maya_skills")
        await _init(db_path)
        maya = KampungAssistant(db_path)
        maya.telegram_fast_responder = ExplodingResponder()
        maya.router.telegram_fast_responder = maya.telegram_fast_responder

        request = (
            "create a skill for opening YouTube in browser, navigating YouTube channels, "
            "reading visible public video lists, and recommending what I should watch"
        )
        asked = await maya.handle_text(request, "telegram")
        _require("draft a new skill scaffold" in asked.lower(), "Maya did not ask before scaffolding")

        created = await maya.handle_text("yes", "telegram")
        _require("created the skill scaffold" in created.lower(), "Maya did not create scaffold after approval")

        skill = await find_skill(db_path, "youtube browser")
        _require(skill is not None and skill["status"] == "proposed", "skill was not stored as proposed")
        scaffold = Path(str(skill["scaffold_path"]))
        text = scaffold.read_text("utf-8").lower()
        _require("trigger:" in text and "non-trigger:" in text, "scaffold missing trigger boundaries")
        _require("hard no:" in text and "success:" in text, "scaffold missing safety or success markers")

        hidden = await maya.skills.build_prompt_context("open youtube channel and recommend videos")
        _require(str(skill["name"]) not in hidden, "proposed skill leaked into active context")

        approved = await maya.handle_text(f"approve skill {skill['skill_id']}", "telegram")
        _require("approved" in approved.lower(), "skill approval failed")

        blocked = await maya.handle_text(f"activate skill {skill['skill_id']}", "telegram")
        _require("activation test" in blocked.lower(), "untested skill activated")

        tested = await maya.handle_text(f"test skill {skill['skill_id']}", "telegram")
        _require("failed:" not in tested.lower(), tested)
        _require("recorded" in tested.lower(), "skill tests were not recorded")

        activated = await maya.handle_text(f"activate skill {skill['skill_id']}", "telegram")
        _require("active" in activated.lower(), "tested skill did not activate")

        relevant = await maya.skills.build_prompt_context("open youtube channel and recommend videos")
        _require(str(skill["name"]) in relevant, "active skill was not selected for matching request")

        unrelated = await maya.skills.build_prompt_context("make me a Word document")
        _require(str(skill["name"]) not in unrelated, "active skill leaked into unrelated request")
    print("youtube_skill_creation_maya_smoke: ok")


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)
    await init_weekly_memory_db(db_path)
    await init_session_memory_db(db_path)
    await init_context_layers_db(db_path)
    await init_workflow_db(db_path)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
