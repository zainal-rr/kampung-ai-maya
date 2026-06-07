from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import presentation_reviewer
from presentation_reviewer import review_presentation_slides
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
