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
    os.environ["OPENAI_COMPLEX_REASONING_EFFORT"] = "medium"
    lanes = ModelLanes()
    fake_mind = FakeMind()
    lanes.mind = fake_mind
    try:
        reply = await lanes.complex_response("think deeply", "", "")
    finally:
        _restore("OPENAI_API_KEY", old_key)
        _restore("OPENAI_COMPLEX_REASONING_EFFORT", old_effort)
    _require(reply == "complex ok", "complex response failed")
    _require(fake_mind.reasoning_effort == "medium", "complex lane did not request medium")
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
