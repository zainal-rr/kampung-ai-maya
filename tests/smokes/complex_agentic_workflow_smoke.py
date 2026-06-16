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
import re
import tempfile
from pathlib import Path

from maya_core.assistant_model_lanes import ModelLanes
from maya_harness.harness_router import HarnessRouter
from maya_harness.harness_store import get_run, init_harness_db, latest_events
from storage import init_db


class FakeMind:
    async def chat(self, messages, reasoning_effort=None):
        return (
            "Summary\n"
            "1. Inspect logs and current workflow state.\n"
            "2. Prepare a safe repair plan.\n"
            "3. Verify before applying anything."
        )


class FakeSteward:
    async def chat(self, messages):
        return "PASS: safe if repo changes remain isolated and restart requires approval."


class FakePremiumSight:
    def __init__(self):
        self.calls = 0

    async def chat(self, messages):
        self.calls += 1
        if self.calls == 2:
            return (
                '[{"agent":"risk_agent","task":"Check safety and approval boundaries."},'
                '{"agent":"test_agent","task":"Define regression tests."}]'
            )
        if "risk_agent" in str(messages):
            return "Risk output"
        if "test_agent" in str(messages):
            return "Test output"
        return "Research context"


async def main() -> None:
    old_openai = os.environ.get("OPENAI_API_KEY")
    old_anthropic = os.environ.get("ANTHROPIC_API_KEY")
    old_google = os.environ.get("GOOGLE_API_KEY")
    os.environ["OPENAI_API_KEY"] = "test"
    os.environ["ANTHROPIC_API_KEY"] = "test"
    os.environ["GOOGLE_API_KEY"] = "test"
    try:
        with tempfile.TemporaryDirectory(prefix="maya-complex-agentic-") as tmp:
            db_path = str(Path(tmp) / "smoke.db")
            await init_db(db_path)
            await init_harness_db(db_path)
            lanes = ModelLanes(db_path)
            lanes.mind = FakeMind()
            lanes.steward = FakeSteward()
            lanes.premium_sight = FakePremiumSight()

            plan_only = await lanes.complex_plan_response("make a plan for architecture", "", "", "telegram")
            _require("Agentic workflow prepared" not in plan_only, "plain plan should not create execution workflow")

            reply = await lanes.complex_plan_response("self heal Maya after approval", "", "", "telegram")
            run_id = _execution_run_id(reply)
            run = await get_run(db_path, run_id)
            _require(run is not None, "agentic harness run missing")
            _require(run["status"] == "paused", "agentic harness run should wait for approval")
            _require(run["workflow_type"] == "self_heal", "self-heal workflow type missing")
            state = run["state"]
            _require(state.get("source_complex_run_id"), "source complex run not linked")
            _require(state.get("pending_approval"), "approval gate missing")
            _require("main-repo apply" in state["pending_approval"].get("details", ""), "repo apply approval boundary missing")
            _require(len(state.get("executable_steps") or []) >= 3, "executable steps missing")

            router = HarnessRouter(db_path)
            approved = await router.handle("yes", "telegram")
            _require(approved and "Self-heal workflow checkpointed" in approved, "approval did not start checkpointed self-heal workflow")
            resumed = await get_run(db_path, run_id)
            _require(resumed is not None and resumed["status"] == "paused", "approved run should pause before isolated mutation")
            _require(resumed["state"].get("self_heal_checkpoint"), "self-heal checkpoint state missing")
            events = await latest_events(db_path, run_id, limit=30)
            event_names = " ".join(item["event"] for item in events)
            _require("snapshot" in event_names and "await_approval" in event_names, "checkpointed execution not recorded")
    finally:
        _restore("OPENAI_API_KEY", old_openai)
        _restore("ANTHROPIC_API_KEY", old_anthropic)
        _restore("GOOGLE_API_KEY", old_google)
    print("complex_agentic_workflow_smoke: ok")


def _execution_run_id(text: str) -> str:
    match = re.search(r"execution workflow:\s*(hrn_[a-f0-9]+)", text)
    if not match:
        raise AssertionError("execution workflow id missing")
    return match.group(1)


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
