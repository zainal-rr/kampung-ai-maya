from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import tempfile
from pathlib import Path

from maya_core.response_style import apply_reply_preferences, format_grouped_answers, split_telegram_segments
from storage import init_db, upsert_preference


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
    asyncio.run(_preference_smoke())

    print("response_style_smoke: ok")


async def _preference_smoke() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-response-style-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        await upsert_preference(db_path, "pref_no_dash", "no dash symbols", source="smoke")
        text = (
            "Path: /Users/zainalabidinjamal/projects/kampung-ai/docs/setup.md\n"
            "Code: `git config --global user.name Zainal`\n"
            "URL: https://example.com/a-b\n"
            "Plain dash - should go"
        )
        styled = await apply_reply_preferences(db_path, text)
        _require("kampung-ai/docs/setup.md" in styled, "file path dash was damaged")
        _require("git config --global" in styled, "inline code dash was damaged")
        _require("https://example.com/a-b" in styled, "URL dash was damaged")
        _require("Plain dash should go" in styled, "plain dash was not removed")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
