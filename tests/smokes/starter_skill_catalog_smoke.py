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

from maya_core.starter_skill_catalog import CATALOG, install_starter_catalog
from maya_core.skill_store import list_custom_skills


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        os.chdir(tmpdir)
        db_path = str(Path(tmpdir) / "test.db")
        count = await install_starter_catalog(db_path)
        assert count == len(CATALOG)
        rows = await list_custom_skills(db_path, status="proposed", limit=20)
        assert len(rows) == len(CATALOG)
        assert (Path(tmpdir) / "maya_skills" / "proposed" / "flight_research.md").exists()
    print("starter_skill_catalog_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
