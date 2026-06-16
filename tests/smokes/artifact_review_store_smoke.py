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

from maya_documents.artifact_review_store import latest_artifact_review_text, record_artifact_review


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-artifact-review-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        empty = await latest_artifact_review_text(db_path)
        _require("No artifact review" in empty, "empty review state should be explicit")
        await record_artifact_review(
            db_path,
            "xlsx",
            "Seoul food trip budget tracker",
            "claude-opus-4-8",
            True,
            "PASS: Workbook has restaurant rows, source links, formulas, and suggestions.",
        )
        text = await latest_artifact_review_text(db_path)
        _require("artifact: xlsx" in text, "artifact type missing")
        _require("reviewer: claude-opus-4-8" in text, "reviewer missing")
        _require("status: PASS" in text, "status missing")
        _require("restaurant rows" in text, "review text missing")
    print("artifact_review_store_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
