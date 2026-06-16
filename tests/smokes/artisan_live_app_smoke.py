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

from maya_core.artisan_runner import create_artisan_implementation_request, latest_artisan_delivery_text
from maya_harness.harness_store import get_run, init_harness_db
from maya_core.storage import init_db


async def main() -> None:
    if os.getenv("RUN_LIVE_ARTISAN_SMOKE") != "1":
        print("artisan_live_app_smoke: skipped (set RUN_LIVE_ARTISAN_SMOKE=1)")
        return
    old_root = os.environ.get("MAYA_WORKSPACE_ROOT")
    old_timeout = os.environ.get("ARTISAN_TIMEOUT_SECONDS")
    with tempfile.TemporaryDirectory(prefix="maya-live-artisan-app-") as tmp:
        root = Path(tmp)
        os.environ["MAYA_WORKSPACE_ROOT"] = str(root / "Maya")
        os.environ["ARTISAN_TIMEOUT_SECONDS"] = os.getenv("ARTISAN_TIMEOUT_SECONDS", "180")
        db_path = str(root / "smoke.db")
        await init_db(db_path)
        await init_harness_db(db_path)
        run_id, reply = await create_artisan_implementation_request(
            db_path,
            "make a tiny habit tracker web app with water, reading, and walking buttons",
            "telegram",
            gemini_build_brief=(
                "Create a static app project folder with index.html, style.css, script.js, and README.md. "
                "The UI must visibly include water, reading, and walking habit buttons. "
                "Use localStorage for counts. Do not use external services."
            ),
        )
        run = await get_run(db_path, run_id)
        _require(run is not None, "run missing")
        _require(run["status"] == "completed", reply + "\n" + str(run["state"]))
        qa = run["state"].get("app_qa") or {}
        _require(qa.get("passed") is True, str(qa))
        delivery = await latest_artisan_delivery_text(db_path, "app", "telegram")
        _require("[file:" in delivery and "Last app:" in delivery, delivery)
    _restore("MAYA_WORKSPACE_ROOT", old_root)
    _restore("ARTISAN_TIMEOUT_SECONDS", old_timeout)
    print("artisan_live_app_smoke: ok")


def _restore(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
