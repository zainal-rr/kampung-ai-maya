from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from artisan_runner import create_artisan_implementation_request
from harness_store import get_run, init_harness_db
from storage import init_db


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
        _require(run["status"] == "completed", "template maker run did not complete")
        _require(state.get("maker_template", {}).get("template_id") == "cable_clip", "maker template not selected")
        _require("timed out" not in state.get("summary", ""), "template path should not wait for a coding engine")
        qa = state.get("maker_qa") or {}
        _require(qa.get("passed") is True, "maker QA did not pass")
        _require(qa.get("blend_files"), "missing blend output")
        _require(qa.get("mesh_files"), "missing mesh output")
        _require(qa.get("readme_files"), "missing readme output")
        _require(qa.get("dimensions_mm"), "missing mesh dimensions")
        _require(qa.get("preview_files"), "missing preview render")
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
