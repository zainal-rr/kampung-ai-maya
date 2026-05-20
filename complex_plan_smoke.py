from __future__ import annotations

import asyncio
import os

from assistant_model_lanes import ModelLanes


class FakeMind:
    def __init__(self):
        self.reasoning_effort = ""

    async def chat(self, messages, reasoning_effort=None):
        self.reasoning_effort = reasoning_effort or ""
        return "Summary\nPlan body"


class FakeSteward:
    async def chat(self, messages):
        return "Review body"


async def main() -> None:
    old_openai = os.environ.get("OPENAI_API_KEY")
    old_anthropic = os.environ.get("ANTHROPIC_API_KEY")
    old_effort = os.environ.get("OPENAI_COMPLEX_REASONING_EFFORT")
    os.environ["OPENAI_API_KEY"] = "test"
    os.environ["ANTHROPIC_API_KEY"] = "test"
    os.environ["OPENAI_COMPLEX_REASONING_EFFORT"] = "xhigh"
    lanes = ModelLanes()
    lanes.mind = FakeMind()
    lanes.steward = FakeSteward()
    try:
        _require(not lanes.should_use_complex_path("architecture strategy"), "silent complex escalation")
        _require(lanes.should_use_complex_path("this is complex architecture strategy"), "explicit complex missed")
        _require(lanes.should_use_plan_path("make a plan for architecture"), "plan path missed")
        reply = await lanes.complex_plan_response("make a plan for architecture", "", "")
        post = await lanes.post_implementation_review("request", "plan", "changed files", "tests passed")
    finally:
        _restore("OPENAI_API_KEY", old_openai)
        _restore("ANTHROPIC_API_KEY", old_anthropic)
        _restore("OPENAI_COMPLEX_REASONING_EFFORT", old_effort)
    _require("Plan body" in reply, "GPT plan missing")
    _require("Steward review" in reply and "Review body" in reply, "Claude review missing")
    _require("Review body" in post, "post implementation review missing")
    _require(lanes.mind.reasoning_effort == "xhigh", "GPT plan did not use xhigh")
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
