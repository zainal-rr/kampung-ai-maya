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

from maya_core.assistant import KampungAssistant
from maya_core.assistant_model_lanes import ModelLanes
from maya_core.lesson_store import init_lesson_db
from routine_store import init_routine_db
from route_tracker import last_route_text
from skill_store import init_skill_db
from storage import create_task, init_db, list_tasks
from storage_tasks import update_task_status


class FakeMind:
    async def chat(self, messages, reasoning_effort=None):
        return (
            "Summary\n"
            "Concrete failure: Core Memory is near capacity.\n"
            "Plan is approval gated and limited to memory self-heal.\n"
            "Key Changes\n"
            "Create a read-only snapshot and propose compacted memory text before any write.\n"
            "Test Plan\n"
            "Verify the snapshot and confirm critical rules remain present.\n"
            "Approval Needed\n"
            "Ask before memory write, cleanup, restart, or patch."
        )


class FakeSteward:
    async def chat(self, messages):
        return "PASS: safe only with approval gates."


class FakePremiumSight:
    def __init__(self):
        self.calls = 0

    async def chat(self, messages):
        self.calls += 1
        if self.calls == 2:
            return '[{"agent":"risk_agent","task":"Check approval boundaries."}]'
        if "risk_agent" in str(messages):
            return "Risk output"
        return "Research context"


async def main() -> None:
    old_openai = os.environ.get("OPENAI_API_KEY")
    old_anthropic = os.environ.get("ANTHROPIC_API_KEY")
    old_google = os.environ.get("GOOGLE_API_KEY")
    os.environ["OPENAI_API_KEY"] = "test"
    os.environ["ANTHROPIC_API_KEY"] = "test"
    os.environ["GOOGLE_API_KEY"] = "test"
    try:
        with tempfile.TemporaryDirectory(prefix="maya-complex-telegram-") as tmp:
            db_path = str(Path(tmp) / "smoke.db")
            await _init(db_path)
            stale_task = await create_task(
                db_path,
                title="Can you update that to 4 days",
                details="Can you update that to 4 days",
                channel="telegram",
                action_type="create_skill_scaffold",
                autonomy_mode="suggest",
                payload="Can you update that to 4 days",
            )
            await update_task_status(db_path, stale_task, "awaiting_confirmation", result="stale approval")

            assistant = KampungAssistant(db_path)
            lanes = ModelLanes(db_path)
            lanes.mind = FakeMind()
            lanes.steward = FakeSteward()
            lanes.premium_sight = FakePremiumSight()
            assistant.model_lanes = lanes

            reply = await assistant.handle_text("[complex]self heal Maya after approval", "telegram", input_type="command")
            _require("Self heal check:" not in reply, "explicit complex was intercepted by normal self-heal")
            _require("Agentic workflow prepared:" in reply, "complex agentic workflow was not prepared")
            route = await last_route_text(db_path)
            _require("lane: GPT 5.5 medium + Claude review" in route, "complex route metadata missing")

            approved = await assistant.handle_text("Yes", "telegram")
            _require("Self heal check:" in approved, "approval did not resume the complex self-heal workflow")
            _require("approved /complex plan" in approved, "self-heal did not use approved complex plan")
            _require("Core Memory is near capacity" in approved, "approved complex plan issue was not preserved")
            _require("Detected: Summary" not in approved, "self-heal issue extraction used a section heading")
            _require("limit: 300 lines" not in approved, "generic code-health self-heal overrode complex plan")
            _require("Can you update that to 4 days" not in approved, "stale skill approval was resolved instead")
            pending = await list_tasks(db_path, statuses=("awaiting_confirmation",), limit=10)
            _require(
                not any(str(item["title"]) == "Review Maya self-heal proposal" for item in pending),
                "agentic self-heal should not create a second stale task approval",
            )
            route = await last_route_text(db_path)
            _require("lane: LangGraph harness" in route, "approval resume should use harness route")
    finally:
        _restore("OPENAI_API_KEY", old_openai)
        _restore("ANTHROPIC_API_KEY", old_anthropic)
        _restore("GOOGLE_API_KEY", old_google)
    print("complex_telegram_route_smoke: ok")


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)


def _restore(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
