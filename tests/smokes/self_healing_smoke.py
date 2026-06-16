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

from self_heal_store import init_self_heal_db, latest_self_heal_report
from self_healing import self_heal_text
from storage import init_db, list_tasks


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-self-heal-") as tmp:
        root = Path(tmp)
        logs = root / "logs"
        logs.mkdir()
        (logs / "error.log").write_text("Traceback: simulated failure\n", encoding="utf-8")
        db_path = str(root / "smoke.db")
        await init_db(db_path)
        await init_self_heal_db(db_path)

        text = await self_heal_text(db_path, root)
        report = await latest_self_heal_report(db_path)
        tasks = await list_tasks(db_path, statuses=("awaiting_confirmation",), limit=5)
        _require("Self heal check:" in text and "proposal only" in text, "self heal reply missing stage")
        _require("ask before patch, deploy, or restart" in text, "self heal reply missing boundary")
        _require(report is not None, "self heal report was not created")
        _require(tasks and tasks[0]["action_type"] == "apply_code_patch", "review task not created")
        print("self_healing_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
