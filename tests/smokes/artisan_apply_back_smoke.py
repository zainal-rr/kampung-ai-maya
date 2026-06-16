from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import json
import subprocess
import tempfile
from pathlib import Path

from maya_core.artisan_apply import apply_latest_artisan_repo_changes
from harness_store import init_harness_db, upsert_run
from storage import init_db


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-artisan-apply-") as tmp:
        root = Path(tmp)
        db_path = str(root / "smoke.db")
        await init_db(db_path)
        await init_harness_db(db_path)
        repo = root / "repo"
        worktree = root / "worktree"
        _make_repo(repo)
        _git(repo, "worktree", "add", "--detach", str(worktree), "HEAD")
        (worktree / "README.md").write_text("# Approval Smoke\n\nPatched by Artisan.\n", encoding="utf-8")
        state = {
            "run_id": "hrn_apply_smoke",
            "thread_id": "maya:artisan",
            "channel": "telegram",
            "workflow_type": "artisan_repo",
            "goal": "patch repo",
            "current_step": 1,
            "working_directory": str(worktree),
            "original_repo_path": str(repo),
            "isolation_mode": "git_worktree",
        }
        await upsert_run(db_path, state, status="approved_waiting_manual_apply")
        reply = await apply_latest_artisan_repo_changes(db_path)
        _require("Applied the approved Artisan repo changes" in reply, reply)
        _require("Patched by Artisan" in (repo / "README.md").read_text("utf-8"), "patch was not applied")
        _require(_git(repo, "status", "--short").stdout.decode().strip() == "M README.md", "patch should not commit")
    print("artisan_apply_back_smoke: ok")


def _make_repo(path: Path) -> None:
    path.mkdir()
    _git(path, "init")
    (path / "README.md").write_text("# Approval Smoke\n", encoding="utf-8")
    _git(path, "add", "README.md")
    _git(path, "-c", "user.name=Smoke", "-c", "user.email=smoke@example.test", "commit", "-m", "initial")


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
