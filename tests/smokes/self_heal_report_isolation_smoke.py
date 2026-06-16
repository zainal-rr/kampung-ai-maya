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

from self_heal_commands import handle_self_heal_status
from self_heal_store import create_self_heal_report, init_self_heal_db, record_self_heal_stage


async def main() -> None:
    with tempfile.NamedTemporaryFile() as tmp:
        db_path = tmp.name
        await init_self_heal_db(db_path)
        report_id = await create_self_heal_report(
            db_path,
            issue="old issue",
            diagnosis="old diagnosis",
            proposed_fix="old fix",
            tests="old tests",
        )
        await record_self_heal_stage(db_path, report_id, "proposed", "old fix")
        await record_self_heal_stage(db_path, None, "closed", "clean later run")
        text = await handle_self_heal_status(db_path, "show the repair report")
        _require(text and "old fix" in text, "report stage missing")
        _require("clean later run" not in text, "unrelated stage leaked into report")
    print("self_heal_report_isolation_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
