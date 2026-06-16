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

from maya_core.self_heal_commands import handle_self_heal_status
from maya_core.self_heal_store import init_self_heal_db, latest_self_heal_stages
from maya_core.self_healing import self_heal_text
from maya_core.storage import init_db


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-self-heal-loop-") as tmp:
        root = Path(tmp)
        (root / "logs").mkdir()
        (root / "logs" / "error.log").write_text("Traceback: simulated failure\n", encoding="utf-8")
        db_path = str(root / "smoke.db")
        await init_db(db_path)
        await init_self_heal_db(db_path)
        await self_heal_text(db_path, root)
        stages = await latest_self_heal_stages(db_path)
        _require([item["status"] for item in stages][-1] == "proposed", "proposal stage missing")
        report = await handle_self_heal_status(db_path, "show the repair report")
        _require(report and "Patch direction:" in report, "repair report missing")
        restart = await handle_self_heal_status(db_path, "is it safe to restart")
        _require(restart and "explicit approval" in restart, "restart boundary missing")
    print("self_heal_loop_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
