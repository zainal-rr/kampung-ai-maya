from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


from maya_core.assistant_model_lanes import ModelLanes
from maya_browser.browser_followup_policy import looks_like_general_question, looks_like_writing_or_advice_request


def main() -> None:
    normal_text = (
        "Write a polite no to a meeting invite because I am overloaded.",
        "Write a manager update: project is on track but waiting for finance approval.",
        "Write a short travel approval policy.",
        "Write a simple SQL query to count tasks by status.",
        "Give me an event-day checklist for a small office workshop.",
        "Should I buy cheaper laptops or fewer better laptops? Give me a practical answer.",
    )
    for text in normal_text:
        _require(not ModelLanes.should_use_artisan_path(text), f"ordinary prompt routed to Artisan: {text}")
    artisan_text = (
        "make an app for tasks",
        "implement this plan",
        "fix this Python error in the repo",
    )
    for text in artisan_text:
        _require(ModelLanes.should_use_artisan_path(text), f"implementation prompt missed Artisan: {text}")
    _require(looks_like_general_question("should i buy cheaper laptops"), "browser should ignore advice questions")
    _require(looks_like_writing_or_advice_request("write a reminder to send the file"), "browser should ignore writing requests")
    print("routing_boundary_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
