from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from assistant import KampungAssistant
from context_layers import init_context_layers_db
from lesson_store import init_lesson_db
from project_store import active_project, project_notes
from route_tracker import init_route_db
from routine_store import init_routine_db
from session_memory_store import init_session_memory_db
from skill_store import find_skill, init_skill_db, list_skill_proposals
from storage import init_db
from weekly_memory_store import init_weekly_memory_db
from workflow_store import init_workflow_db


class ExplodingResponder:
    async def chat(self, messages):
        raise AssertionError("provider fallback should not be called")


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-hardening-") as tmp:
        tmp_path = Path(tmp)
        project_root = tmp_path / "projects"
        alpha = project_root / "orchid-alpha"
        beta = project_root / "orchid-beta"
        alpha.mkdir(parents=True)
        beta.mkdir(parents=True)
        os.environ["MAYA_PROJECT_ROOTS"] = str(project_root)
        db_path = str(tmp_path / "smoke.db")
        await _init(db_path)

        maya = KampungAssistant(db_path)
        maya.telegram_fast_responder = ExplodingResponder()
        maya.router.telegram_fast_responder = maya.telegram_fast_responder
        maya.commands.documents.workspace = tmp_path / "Kampung AI"

        loose_yes = await maya.handle_text("yes", "telegram")
        _require("nothing is waiting" in loose_yes.lower(), "loose yes fell through")
        loose_no = await maya.handle_text("no that is okay", "telegram")
        _require("nothing is waiting" in loose_no.lower(), "loose no fell through")

        ambiguous = await maya.handle_text("open project orchid", "telegram")
        _require("more than one" in ambiguous.lower() and "orchid-beta" in ambiguous, "ambiguous project not listed")
        second_path = Path(ambiguous.splitlines()[2].split(" at ", 1)[1])
        selected = await maya.handle_text("2", "telegram")
        _require(str(second_path) in selected, "numbered project choice failed")
        project = await active_project(db_path)
        _require(project is not None and project.path == second_path, "active project not persisted")
        await maya.handle_text("new topic", "telegram")
        still_active = await maya.handle_text("what project are we in", "telegram")
        _require(project.name in still_active, "new topic cleared project")

        project_doc = await maya.handle_text("create an md file for this project about setup", "telegram")
        _require(str(second_path / "docs") in project_doc, "project document did not land in docs")
        notes = await project_notes(db_path, second_path, limit=2)
        _require(any("setup.md" in item["content"] for item in notes), "project document memory missing")
        await maya.handle_text("close project", "telegram")
        no_project_doc = await maya.handle_text("create an md file for this project about setup", "telegram")
        _require("no active project" in no_project_doc.lower(), "this-project guardrail failed")

        missing = await maya.handle_text("book me a hotel in Penang tomorrow", "telegram")
        _require("draft the missing skill" in missing.lower(), "missing skill did not ask")
        declined = await maya.handle_text("no", "telegram")
        _require("won't do" in declined.lower(), "skill decline failed")
        missing_again = await maya.handle_text("book me a hotel in Penang tomorrow", "telegram")
        _require("draft the missing skill" in missing_again.lower(), "second missing skill did not ask")
        approved = await maya.handle_text("yes", "telegram")
        _require("skill scaffold" in approved.lower(), "skill approval did not scaffold")
        proposals = await list_skill_proposals(db_path, limit=5)
        _require(proposals and "hotel" in proposals[0]["summary"].lower(), "skill proposal missing")

        proposal_context = await maya.skills.build_prompt_context("hotel booking")
        _require("hotel" not in proposal_context.lower(), "proposed skill leaked into active context")
        approved_skill = await maya.handle_text("approve skill hotel booking", "telegram")
        _require("approved" in approved_skill.lower(), "skill approve command failed")
        still_hidden = await maya.skills.build_prompt_context("hotel booking")
        _require("hotel" not in still_hidden.lower(), "approved skill leaked before activation")
        activated = await maya.handle_text("activate skill hotel booking", "telegram")
        _require("activation test" in activated.lower(), "untested skill should not activate")
        skill = await find_skill(db_path, "hotel booking")
        _require(skill and skill.get("scaffold_path"), "skill scaffold path missing")
        _write_reviewed_scaffold(Path(str(skill["scaffold_path"])))
        tested = await maya.handle_text("test skill hotel booking", "telegram")
        _require("recorded" in tested.lower(), "skill activation test missing")
        activated = await maya.handle_text("activate skill hotel booking", "telegram")
        _require("active" in activated.lower(), "skill activation failed")
        active_context = await maya.skills.build_prompt_context("hotel booking")
        _require("hotel" in active_context.lower(), "active skill missing from context")
        disabled = await maya.handle_text("disable skill hotel booking", "telegram")
        _require("disabled" in disabled.lower(), "skill disable failed")
        disabled_context = await maya.skills.build_prompt_context("hotel booking")
        _require("hotel" not in disabled_context.lower(), "disabled skill leaked into context")
        print("hardening_flow_smoke: ok")


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)
    await init_route_db(db_path)
    await init_weekly_memory_db(db_path)
    await init_session_memory_db(db_path)
    await init_context_layers_db(db_path)
    await init_workflow_db(db_path)


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
