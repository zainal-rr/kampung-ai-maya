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

from maya_harness.harness_artifact_store import latest_artifacts, record_structured_artifact
from maya_harness.harness_models import local_artifact
from maya_harness.harness_store import init_harness_db


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-artifacts-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        file_path = Path(tmp) / "note.md"
        file_path.write_text("# Note\n", encoding="utf-8")
        await init_harness_db(db_path)
        await record_structured_artifact(
            db_path,
            "run_1",
            local_artifact("note", str(file_path), "test note", "smoke"),
        )
        rows = await latest_artifacts(db_path, "run_1")
        _require(rows and rows[0]["kind"] == "note", "artifact kind missing")
        _require(rows[0]["exists_status"] == "exists", "artifact existence not tracked")
        _require(rows[0]["checksum"], "artifact checksum missing")
    print("harness_artifact_tracking_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
