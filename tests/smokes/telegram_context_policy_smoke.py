from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


from maya_telegram.telegram_context_policy import should_use_full_context, silent_context_guard


def main() -> None:
    _require(
        not should_use_full_context("How should I score vendors fairly?", channel="telegram"),
        "normal Telegram Q&A should not receive full durable context",
    )
    _require(
        not should_use_full_context("Compare OpenHands and Claude Code briefly.", channel="telegram"),
        "normal product comparisons should not receive full durable context",
    )
    _require(
        should_use_full_context("what office Telegram style do I prefer?", channel="telegram"),
        "direct preference recall should receive memory context",
    )
    _require(
        should_use_full_context("make me a Word document", channel="telegram"),
        "document creation should receive artifact context",
    )
    guarded = silent_context_guard("Saved facts:\n- private support context")
    _require("Use this support context silently" in guarded, "silent context guard missing")
    print("telegram_context_policy_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
