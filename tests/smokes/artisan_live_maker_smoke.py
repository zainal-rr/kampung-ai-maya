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

from artisan_runner import create_artisan_implementation_request, latest_artisan_delivery_text
from harness_store import get_run, init_harness_db
from storage import init_db


async def main() -> None:
    old_root = os.environ.get("MAYA_WORKSPACE_ROOT")
    with tempfile.TemporaryDirectory(prefix="maya-live-artisan-maker-") as tmp:
        root = Path(tmp)
        os.environ["MAYA_WORKSPACE_ROOT"] = str(root / "Maya")
        db_path = str(root / "smoke.db")
        await init_db(db_path)
        await init_harness_db(db_path)
        run_id, reply = await create_artisan_implementation_request(
            db_path,
            "make a small wall hook for 3D printing. Save STL, Blender file, preview, and README.",
            "telegram",
            gemini_build_brief="Known simple wall hook maker request. Use millimeters. Stop before slicing or physical print.",
        )
        run = await get_run(db_path, run_id)
        _require(run is not None, "run missing")
        _require(run["status"] == "completed", reply + "\n" + str(run["state"]))
        qa = run["state"].get("maker_qa") or {}
        _require(qa.get("passed") is True, str(qa))
        _require(qa.get("mesh_files") and qa.get("blend_files") and qa.get("preview_files"), str(qa))
        delivery = await latest_artisan_delivery_text(db_path, "maker", "telegram")
        _require("[file:" in delivery and "not sliced" in delivery, delivery)
    _restore("MAYA_WORKSPACE_ROOT", old_root)
    print("artisan_live_maker_smoke: ok")


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
