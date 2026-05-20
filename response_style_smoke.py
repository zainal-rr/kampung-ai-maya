from __future__ import annotations

from response_style import format_grouped_answers, split_telegram_segments


def main() -> None:
    outline_lesson = (
        "where is the structure in your words:\n"
        "1)\n"
        "a)\n"
        "b)\n"
        "2)\n"
        "a)\n"
        "b)\n"
        "etc"
    )
    segments = split_telegram_segments(outline_lesson)
    _require(segments == [outline_lesson], "outline examples should stay as one message")

    bundled = "1) what did you learn from me today\n2) tell me my preference"
    segments = split_telegram_segments(bundled)
    _require(
        segments == ["what did you learn from me today", "tell me my preference"],
        "real bundled questions should still split",
    )

    answer = format_grouped_answers(["1) My bad, fixed", "2) Right, noted"])
    _require("1) 1)" not in answer, "grouped answers should not double-number first lines")
    _require("2) 2)" not in answer, "grouped answers should not double-number later lines")

    print("response_style_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
