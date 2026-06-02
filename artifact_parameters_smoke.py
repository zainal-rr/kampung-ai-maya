from __future__ import annotations

from artifact_parameters import artifact_parameter_question


def main() -> None:
    _expect("docx", "Seoul food trip", "")
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
