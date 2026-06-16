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

from harness_models import GroundedObservation
from harness_observation_store import latest_observation, record_observation
from harness_store import init_harness_db


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-grounding-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_harness_db(db_path)
        observation = GroundedObservation(
            source="browser_screen",
            frontmost_app="Google Chrome",
            page_title="Example",
            url="https://example.com",
            screen_summary="Example page visible",
            confidence=0.8,
            provenance=("dom", "screen"),
        )
        await record_observation(db_path, "run_1", observation)
        row = await latest_observation(db_path, "run_1")
        _require(row is not None, "observation missing")
        _require(row["observation"]["frontmost_app"] == "Google Chrome", "frontmost app missing")
        _require("screen" in row["observation"]["provenance"], "provenance missing")
    print("harness_grounding_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
