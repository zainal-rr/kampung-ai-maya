from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from maya_desk import build_maya_desk
from skill_store import init_skill_db, upsert_skill
from storage import init_db


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
