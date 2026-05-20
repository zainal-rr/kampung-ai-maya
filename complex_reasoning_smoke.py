from __future__ import annotations

import asyncio
import os

from assistant_model_lanes import ModelLanes


class FakeMind:
    def __init__(self):
        self.reasoning_effort = ""

    async def chat(self, messages, reasoning_effort=None):
        self.reasoning_effort = reasoning_effort or ""
        return "complex ok"


async def main() -> None:
    old_key = os.environ.get("OPENAI_API_KEY")
    old_effort = os.environ.get("OPENAI_COMPLEX_REASONING_EFFORT")
    os.environ["OPENAI_API_KEY"] = "test"
    os.environ["OPENAI_COMPLEX_REASONING_EFFORT"] = "xhigh"
    lanes = ModelLanes()
    fake_mind = FakeMind()
    lanes.mind = fake_mind
    try:
        reply = await lanes.complex_response("think deeply", "", "")
    finally:
        _restore("OPENAI_API_KEY", old_key)
        _restore("OPENAI_COMPLEX_REASONING_EFFORT", old_effort)
    _require(reply == "complex ok", "complex response failed")
    _require(fake_mind.reasoning_effort == "xhigh", "complex lane did not request xhigh")
    print("complex_reasoning_smoke: ok")


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
