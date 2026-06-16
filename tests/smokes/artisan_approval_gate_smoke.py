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
import subprocess
import tempfile
from pathlib import Path

from artisan_runner import create_artisan_implementation_request
from harness_router import HarnessRouter
from harness_store import get_run, init_harness_db
from storage import init_db


async def main() -> None:
    old_dry = os.environ.get("ARTISAN_DRY_RUN")
    old_root = os.environ.get("MAYA_WORKSPACE_ROOT")
    os.environ["ARTISAN_DRY_RUN"] = "1"
    with tempfile.TemporaryDirectory(prefix="maya-artisan-approval-") as tmp:
        root = Path(tmp)
        os.environ["MAYA_WORKSPACE_ROOT"] = str(root / "Maya")
        db_path = str(root / "smoke.db")
        await init_db(db_path)
        await init_harness_db(db_path)
        repo = _make_repo(root / "repo")
        old_cwd = Path.cwd()
        try:
            os.chdir(repo)
            run_id, _ = await create_artisan_implementation_request(
                db_path,
                "repair this repo",
                "telegram",
                gemini_build_brief="Gemini brief: patch the repo in isolation.",
            )
        finally:
            os.chdir(old_cwd)
        approved = await HarnessRouter(db_path).handle("yes", "telegram")
        _require(approved is not None, "approval did not resolve")
        _require("did not apply" in approved, "approval should not auto-apply repo changes")
        run = await get_run(db_path, run_id)
        _require(run and run["status"] == "approved_waiting_manual_apply", "approval status not recorded safely")
    _restore("ARTISAN_DRY_RUN", old_dry)
    _restore("MAYA_WORKSPACE_ROOT", old_root)
    print("artisan_approval_gate_smoke: ok")


def _make_repo(path: Path) -> Path:
    path.mkdir()
    _git(path, "init")
    (path / "README.md").write_text("# Approval Smoke\n", encoding="utf-8")
    _git(path, "add", "README.md")
    _git(path, "-c", "user.name=Smoke", "-c", "user.email=smoke@example.test", "commit", "-m", "initial")
    return path


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


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
