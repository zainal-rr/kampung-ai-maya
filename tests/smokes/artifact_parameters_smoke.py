from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


from artifact_parameters import artifact_parameter_question


def main() -> None:
    _expect("docx", "Seoul food trip", "")
    _expect("docx", "solo trip food for two days", "Which city or destination")
    _expect("docx", "travel itinerary", "Which city or destination")
    _expect("docx", "Kyoto travel itinerary", "How many days")
    _expect("docx", "router setup guide", "")
    _expect("docx", "technical guide", "What system")
    _expect("docx", "proposal doc", "What is the proposal")
    _expect("docx", "proposal doc for Kampung AI quality", "")
    _expect("docx", "research brief", "What topic")
    _expect("docx", "research brief about Gemini image generation", "")
    _expect("docx", "refund request letter", "")
    _expect("docx", "letter", "What should the letter")
    _expect("xlsx", "budget tracker", "What should the budget")
    _expect("xlsx", "Seoul food budget tracker", "")
    _expect("pptx", "slides", "What topic")
    _expect("pptx", "Seoul food trip", "")
    print("artifact_parameters_smoke: ok")


def _expect(kind: str, topic: str, expected: str) -> None:
    result = artifact_parameter_question(kind, topic, "telegram")
    if expected:
        _require(expected in result, f"{kind} {topic!r} returned {result!r}, expected question containing {expected!r}")
    else:
        _require(result == "", f"{kind} {topic!r} should not ask, got {result!r}")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
