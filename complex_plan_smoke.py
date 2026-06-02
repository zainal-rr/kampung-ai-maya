from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from assistant_model_lanes import ModelLanes
from complex_workflow import complex_workflow_status


class FakeMind:
    def __init__(self):
        self.reasoning_effort = ""
        self.messages = []

    async def chat(self, messages, reasoning_effort=None):
        self.reasoning_effort = reasoning_effort or ""
        self.messages = messages
        return "Summary\nPlan body"


class FakeSteward:
    async def chat(self, messages):
        return "Review body"


class FakePremiumSight:
    def __init__(self):
        self.calls = 0

    async def chat(self, messages):
        self.calls += 1
        if self.calls == 2:
            return (
                '[{"agent":"risk_agent","task":"Find hidden risks."},'
                '{"agent":"test_agent","task":"Find verification checks."}]'
            )
        if "risk_agent" in str(messages):
            return "Risk output"
        if "test_agent" in str(messages):
            return "Test output"
        return "Research context body"


async def main() -> None:
    old_openai = os.environ.get("OPENAI_API_KEY")
    old_anthropic = os.environ.get("ANTHROPIC_API_KEY")
    old_google = os.environ.get("GOOGLE_API_KEY")
    old_effort = os.environ.get("OPENAI_COMPLEX_REASONING_EFFORT")
    os.environ["OPENAI_API_KEY"] = "test"
    os.environ["ANTHROPIC_API_KEY"] = "test"
    os.environ["GOOGLE_API_KEY"] = "test"
    os.environ["OPENAI_COMPLEX_REASONING_EFFORT"] = "medium"
    with tempfile.TemporaryDirectory(prefix="maya-complex-plan-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        lanes = ModelLanes(db_path)
        lanes.mind = FakeMind()
        lanes.steward = FakeSteward()
        lanes.premium_sight = FakePremiumSight()
        try:
            _require(not lanes.should_use_complex_path("architecture strategy"), "silent complex escalation")
            _require(lanes.should_use_complex_path("this is complex architecture strategy"), "explicit complex missed")
            _require(lanes.should_use_plan_path("make a plan for architecture"), "plan path missed")
            reply = await lanes.complex_plan_response("make a plan for architecture", "", "")
            post = await lanes.post_implementation_review("request", "plan", "changed files", "tests passed")
            run_id = reply.rsplit("Workflow:", 1)[1].strip()
            workflow = await complex_workflow_status(db_path, run_id)
        finally:
            _restore("OPENAI_API_KEY", old_openai)
            _restore("ANTHROPIC_API_KEY", old_anthropic)
            _restore("GOOGLE_API_KEY", old_google)
            _restore("OPENAI_COMPLEX_REASONING_EFFORT", old_effort)
    _require("Plan body" in reply, "GPT plan missing")
    _require("Research context body" in str(lanes.mind.messages), "Gemini premium research context missing")
    _require("Steward review" in reply and "Review body" in reply, "Claude review missing")
    _require("Workflow:" in reply, "complex workflow id missing")
    _require("research_agent_finished" in workflow, "research subagent was not recorded")
    _require("graph_planner_agent_finished" in workflow, "graph planner was not recorded")
    _require("task_graph_ready" in workflow, "dynamic task graph was not recorded")
    _require("risk_agent_finished" in workflow, "parallel risk subagent was not recorded")
    _require("test_agent_finished" in workflow, "parallel test subagent was not recorded")
    _require("planner_agent_finished" in workflow, "planner subagent was not recorded")
    _require("review_agent_finished" in workflow, "review subagent was not recorded")
    _require("Review body" in post, "post implementation review missing")
    _require(lanes.mind.reasoning_effort == "medium", "GPT plan did not use medium")
    print("complex_plan_smoke: ok")


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
