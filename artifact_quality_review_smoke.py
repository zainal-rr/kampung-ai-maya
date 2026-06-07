from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import artifact_quality
from artifact_quality import review_artifact_quality
from storage import init_db


class FailingSteward:
    def __init__(self, *args, **kwargs):
        pass

    async def chat(self, messages):
        raise RuntimeError("provider failed with sensitive raw detail")


async def main() -> None:
    old_key = os.environ.get("ANTHROPIC_API_KEY")
    old_steward = artifact_quality.TheSteward
    os.environ["ANTHROPIC_API_KEY"] = "test"
    artifact_quality.TheSteward = FailingSteward
    try:
        with tempfile.TemporaryDirectory(prefix="maya-artifact-review-") as tmp:
            db_path = str(Path(tmp) / "smoke.db")
            await init_db(db_path)
            result = await review_artifact_quality(db_path, "xlsx", "monthly budget", "Sheet content")
            _require(result.passed, "review provider failure should fail open to local QA")
            _require("Claude review unavailable" in result.summary, "clean unavailable summary missing")
            _require("provider failed with sensitive raw detail" not in result.summary, "raw provider error leaked into summary")
    finally:
        artifact_quality.TheSteward = old_steward
        if old_key is None:
            os.environ.pop("ANTHROPIC_API_KEY", None)
        else:
            os.environ["ANTHROPIC_API_KEY"] = old_key
    print("artifact_quality_review_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
