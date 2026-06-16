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
import tempfile
from pathlib import Path

import maya_core.presentation_reviewer as presentation_reviewer
from maya_core.presentation_reviewer import review_presentation_slides
from storage import init_db


class FailingSteward:
    def __init__(self, *args, **kwargs):
        pass

    async def chat(self, messages):
        raise RuntimeError("provider failed")


async def main() -> None:
    old_key = os.environ.get("ANTHROPIC_API_KEY")
    old_steward = presentation_reviewer.TheSteward
    os.environ["ANTHROPIC_API_KEY"] = "test"
    presentation_reviewer.TheSteward = FailingSteward
    try:
        with tempfile.TemporaryDirectory(prefix="maya-presentation-reviewer-") as tmp:
            db_path = str(Path(tmp) / "smoke.db")
            await init_db(db_path)
            slides = [("Tokyo Food Trip", ["Market breakfast", "Cafe route"])]
            reviewed = await review_presentation_slides(db_path, "Tokyo Food Trip", slides)
            _require(reviewed == slides, "failed Claude presentation review should return original slides")
    finally:
        presentation_reviewer.TheSteward = old_steward
        if old_key is None:
            os.environ.pop("ANTHROPIC_API_KEY", None)
        else:
            os.environ["ANTHROPIC_API_KEY"] = old_key
    print("presentation_reviewer_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
