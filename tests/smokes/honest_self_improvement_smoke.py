from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


from maya_core.self_improvement_policy import approval_needed_message, blocks_vague_claim, enforce_honest_claims, failure_notice, verified_learning_message


def main() -> None:
    _require("cannot say I learned" in verified_learning_message("preference", False), "unverified learning not blocked")
    _require(verified_learning_message("preference", True) == "I learned and saved a preference.", "preference message wrong")
    _require("approval" in approval_needed_message(), "approval message missing")
    _require(failure_notice("Flight Search", 2) == "I noticed Flight Search failed 2 times.", "failure notice wrong")
    _require(blocks_vague_claim("I'll remember that"), "vague remember claim not detected")
    _require(blocks_vague_claim("I improved myself"), "vague improvement claim not detected")
    _require(blocks_vague_claim("Skill updated"), "vague skill update claim not detected")
    _require("verifying" in enforce_honest_claims("I'll remember that"), "vague remember claim not rewritten")
    _require("verifying" in enforce_honest_claims("i'll remember that"), "lowercase remember claim not rewritten")
    _require("review" in enforce_honest_claims("i improved myself"), "lowercase improve claim not rewritten")
    print("honest_self_improvement_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
