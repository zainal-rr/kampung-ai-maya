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
import shutil
import subprocess
import tempfile
from pathlib import Path

import aiosqlite

from maya_core.artisan_runner import (
    _codex_chatgpt_auth_state,
    classify_artisan_request,
    create_artisan_implementation_request,
    latest_artisan_summary_text,
)
from maya_harness.harness_store import get_run, init_harness_db
from maya_core.storage import init_db, upsert_preference


async def main() -> None:
    old_dry = os.environ.get("ARTISAN_DRY_RUN")
    old_root = os.environ.get("MAYA_WORKSPACE_ROOT")
    os.environ["ARTISAN_DRY_RUN"] = "1"
    with tempfile.TemporaryDirectory(prefix="maya-artisan-") as tmp:
        os.environ["MAYA_WORKSPACE_ROOT"] = str(Path(tmp) / "Maya")
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        await init_harness_db(db_path)

        _require(classify_artisan_request("make me a habit tracker app") == "artisan_app", "app route failed")
        _require(classify_artisan_request("make a phone stand for 3d printing") == "artisan_3d", "3D route failed")
        if shutil.which("codex"):
            ok, status = _codex_chatgpt_auth_state()
            _require(ok, f"Codex should be logged in using ChatGPT for Artisan runs: {status}")

        run_id, reply = await create_artisan_implementation_request(
            db_path,
            "make me a simple habit tracker app",
            "telegram",
            gemini_build_brief="Gemini brief: create a Vite habit tracker in a real project folder.",
        )
        _require("Artisan" in reply, "reply should name Artisan")
        _require("Codex" not in reply, "reply should not expose the internal engine")
        run = await get_run(db_path, run_id)
        _require(run is not None, "run missing")
        _require(run["workflow_type"] == "artisan_app", "wrong workflow type")
        _require("Gemini brief" in run["state"]["gemini_build_brief"], "brief not stored")
        _require("codex" in run["state"]["summary"].lower(), "dry run summary missing Codex")

        status = await latest_artisan_summary_text(db_path)
        _require(run_id in status and "artisan_app" in status, "latest status missing app run")
        await _latest_target_continuity_case(db_path, Path(tmp))

        await _repo_isolation_case(db_path, Path(tmp))

    _restore("ARTISAN_DRY_RUN", old_dry)
    _restore("MAYA_WORKSPACE_ROOT", old_root)
    print("artisan_runner_smoke: ok")


async def _repo_isolation_case(db_path: str, tmp: Path) -> None:
    repo = tmp / "repo"
    repo.mkdir()
    _git(repo, "init")
    (repo / "README.md").write_text("# Smoke\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "-c", "user.name=Smoke", "-c", "user.email=smoke@example.test", "commit", "-m", "initial")
    old_cwd = Path.cwd()
    try:
        os.chdir(repo)
        run_id, reply = await create_artisan_implementation_request(
            db_path,
            "fix a bug in this repo",
            "telegram",
            gemini_build_brief="Gemini brief: inspect and patch in isolation.",
        )
    finally:
        os.chdir(old_cwd)
    run = await get_run(db_path, run_id)
    _require(run is not None, "repo run missing")
    state = run["state"]
    _require(run["status"] == "paused", "repo run should pause for approval")
    _require(state["workflow_type"] == "artisan_repo", "repo workflow type missing")
    _require(state["isolation_mode"] == "git_worktree", "repo job did not use git worktree isolation")
    _require(Path(state["working_directory"]) != repo, "repo job targeted the main repo")
    _require(Path(state["original_repo_path"]) == repo.resolve(), "original repo path not recorded")
    _require("repo_approval_required" in reply, "reply missing approval gate")
    approvals = await _pending_approvals(db_path, run_id)
    _require(approvals and "Isolated worktree:" in approvals[0], "pending repo approval missing worktree details")


async def _latest_target_continuity_case(db_path: str, tmp: Path) -> None:
    app = tmp / "Maya" / "Projects" / "existing-app"
    maker = tmp / "Maya" / "Projects" / "existing-model" / "3d"
    app.mkdir(parents=True)
    maker.mkdir(parents=True)
    await upsert_preference(db_path, "maya_last_app_project_path", str(app), "smoke")
    await upsert_preference(db_path, "maya_last_maker_project_path", str(maker), "smoke")
    app_run, _ = await create_artisan_implementation_request(
        db_path,
        "edit the last app to add dark mode",
        "telegram",
        gemini_build_brief="Gemini brief: edit latest app in place.",
    )
    maker_run, _ = await create_artisan_implementation_request(
        db_path,
        "edit the last 3D model to be wider",
        "telegram",
        gemini_build_brief="Gemini brief: edit latest maker model in place.",
    )
    app_state = (await get_run(db_path, app_run))["state"]
    maker_state = (await get_run(db_path, maker_run))["state"]
    _require(Path(app_state["working_directory"]) == app, "latest app edit did not target existing app")
    _require(Path(maker_state["working_directory"]) == maker, "latest maker edit did not target existing model")


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


async def _pending_approvals(db_path: str, run_id: str) -> list[str]:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            SELECT details
            FROM harness_approvals
            WHERE run_id = ? AND action = 'apply_artisan_repo_changes' AND status = 'pending'
            """,
            (run_id,),
        )
        rows = await cursor.fetchall()
    return [str(row[0]) for row in rows]


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
