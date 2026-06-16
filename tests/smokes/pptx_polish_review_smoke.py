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

import maya_documents.pptx_polish_review as pptx_polish_review
from maya_documents.office_modern_files import create_pptx
from maya_documents.pptx_polish_review import claude_polish_grade
from maya_core.storage import init_db


class FailingSteward:
    def __init__(self, *args, **kwargs):
        pass

    async def chat(self, messages):
        raise RuntimeError("provider failed")


async def main() -> None:
    old_key = os.environ.get("ANTHROPIC_API_KEY")
    old_steward = pptx_polish_review.TheSteward
    os.environ["ANTHROPIC_API_KEY"] = "test"
    pptx_polish_review.TheSteward = FailingSteward
    try:
        with tempfile.TemporaryDirectory(prefix="maya-pptx-polish-") as tmp:
            root = Path(tmp)
            db_path = str(root / "smoke.db")
            await init_db(db_path)
            deck = root / "deck.pptx"
            create_pptx(
                deck,
                "Tokyo Food Trip Deck",
                [
                    ("Tokyo In 48 Hours", ["Market breakfast", "Cafe route", "Dinner anchor"]),
                    ("Use Neighborhood Anchors", ["Tsukiji morning", "Ginza lunch", "Shinjuku dinner"]),
                    ("Keep The Budget Visible", ["KRW daily budget", "One splurge meal", "Cash buffer"]),
                ],
            )
            polish, used_claude = await claude_polish_grade(db_path, deck)
            _require(not used_claude, "failed Claude polish review should report unavailable")
            _require("Claude polish review unavailable" in polish, "clean polish-unavailable message missing")
            _require("provider failed" not in polish, "raw provider error leaked into polish")
    finally:
        pptx_polish_review.TheSteward = old_steward
        if old_key is None:
            os.environ.pop("ANTHROPIC_API_KEY", None)
        else:
            os.environ["ANTHROPIC_API_KEY"] = old_key
    print("pptx_polish_review_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
