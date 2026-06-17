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

from maya_core.artisan_runner import create_artisan_implementation_request
from maya_harness.harness_store import get_run, init_harness_db
from maya_core.storage import init_db


async def main() -> None:
    old_root = os.environ.get("MAYA_WORKSPACE_ROOT")
    with tempfile.TemporaryDirectory(prefix="maya-artisan-template-") as tmp:
        root = Path(tmp)
        os.environ["MAYA_WORKSPACE_ROOT"] = str(root / "Maya")
        db_path = str(root / "smoke.db")
        await init_db(db_path)
        await init_harness_db(db_path)
        run_id, reply = await create_artisan_implementation_request(
            db_path,
            "make a tiny 3D printable 5mm cable clip in Blender. Save STL and README.",
            "telegram",
            gemini_build_brief="Gemini brief: known simple maker request for a 5mm cable clip. Stop before physical print.",
        )
        run = await get_run(db_path, run_id)
        _require(run is not None, "run missing")
        state = run["state"]
        _require(state.get("maker_template", {}).get("template_id") == "cable_clip", "maker template not selected")
        _require("timed out" not in state.get("summary", ""), "template path should not wait for a coding engine")
        qa = state.get("maker_qa") or {}
        if state.get("blender_available"):
            _require(run["status"] == "completed", "template maker run did not complete")
            _require(qa.get("passed") is True, "maker QA did not pass")
            _require(qa.get("blend_files"), "missing blend output")
            _require(qa.get("mesh_files"), "missing mesh output")
            _require(qa.get("dimensions_mm"), "missing mesh dimensions")
            _require(qa.get("preview_files"), "missing preview render")
        else:
            _require(run["status"] == "failed", "missing Blender should fail export QA honestly")
            _require(qa.get("passed") is False, "missing Blender should not pass maker QA")
            _require(qa.get("source_scripts"), "missing fallback/source script")
            issues = "\n".join(qa.get("issues") or [])
            _require("Blender binary not found" in issues, "missing Blender issue was not reported")
            _require(not qa.get("blend_files"), "missing Blender should not claim blend output")
            _require(not qa.get("mesh_files"), "missing Blender should not claim mesh output")
        _require(qa.get("readme_files"), "missing readme output")
        _require("maya-template-cable-clip" in reply, "reply did not show template output files")
    _restore("MAYA_WORKSPACE_ROOT", old_root)
    print("artisan_maker_template_smoke: ok")


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
