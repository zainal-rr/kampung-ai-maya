from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


from maya_core.markdown_drafter import _assumed_role, _prompt


def main() -> None:
    travel = _prompt("travel document for Kyoto and Osaka")
    drone = _prompt("drone inspection company proposal")
    budget = _prompt("Excel budget tracker for monthly expenses")
    _require("traveller and trip planner" in travel, "travel role missing")
    _require("drone operations company" in drone, "drone role missing")
    _require("manage the budget" in budget, "budget role missing")
    for prompt in (travel, drone, budget):
        _require("Write from inside that role" in prompt, "role embodiment instruction missing")
        _require("assumptions" in prompt.lower(), "assumptions instruction missing")
        _require("constraints" in prompt.lower(), "constraints key point missing")
        _require("risks" in prompt.lower(), "risks key point missing")
        _require("next actions" in prompt.lower(), "next actions key point missing")
    _require("drone operations company" in _assumed_role("drone mapping plan"), "drone role helper failed")
    print("markdown_drafter_prompt_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
