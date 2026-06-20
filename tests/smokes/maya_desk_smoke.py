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

from maya_core.maya_desk import build_maya_desk
from maya_core.skill_store import init_skill_db, upsert_skill
from maya_core.storage import init_db


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["MAYA_WORKSPACE_ROOT"] = str(Path(tmpdir) / "Maya")
        db_path = str(Path(tmpdir) / "test.db")
        await init_db(db_path)
        await init_skill_db(db_path)
        await upsert_skill(db_path, "sample", "Sample", "Demo", "safe", "none", "active", "test")
        path = Path(await build_maya_desk(db_path))
        assert path.exists()
        html = path.read_text("utf-8")
        assert "Maya Desk" in html
        for section in (
            "Readiness",
            "Proof Boundary Snapshot",
            "Operational Score Estimate",
            "Pending Physical Or Live Proof",
            "Workflows",
            "Last Route",
            "Memory Health",
            "Weekly Memory",
            "Dependency Readiness",
            "Provider Readiness",
            "Latest Passing Demos",
            "Live Test Evidence",
            "7-Day Reliability Soak",
            "30-Day Reliability Scorecard",
            "Browser Field Tests",
            "Browser Benchmark",
            "Route And Cost Audit",
            "Hardening Audit",
            "Trace Metrics",
            "Harness Traces",
            "Recent Failures",
            "Failure Trace Metrics",
            "Cost",
        ):
            assert section in html
        assert "Sample" in html
        assert "sk-" not in html
        assert "BEGIN PRIVATE KEY" not in html
        assert str(path).endswith("reports/maya-desk.html")
    print("maya_desk_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
