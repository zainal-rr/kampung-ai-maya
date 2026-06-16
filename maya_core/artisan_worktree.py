from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from maya_documents.office_files import safe_slug
from maya_core.workspace_paths import workspace_dir


@dataclass(frozen=True)
class RepoIsolation:
    original_repo: Path
    worktree_path: Path
    base_ref: str
    dirty_summary: str


def create_repo_isolation(source: Path, run_id: str) -> RepoIsolation | None:
    if not shutil.which("git"):
        return None
    repo = git_root(source)
    if repo is None:
        return None
    base_ref = _git_output(repo, "rev-parse", "--short", "HEAD")
    if not base_ref:
        return None
    root = _worktree_root()
    root.mkdir(parents=True, exist_ok=True)
    worktree = root / f"{safe_slug(repo.name, 42)}-{safe_slug(run_id, 24)}"
    if worktree.exists():
        return RepoIsolation(repo, worktree, base_ref, _dirty_summary(repo))
    try:
        subprocess.run(
            ["git", "-C", str(repo), "worktree", "add", "--detach", str(worktree), "HEAD"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (subprocess.CalledProcessError, OSError):
        return None
    return RepoIsolation(repo, worktree, base_ref, _dirty_summary(repo))


def git_root(path: Path) -> Path | None:
    output = _git_output(path, "rev-parse", "--show-toplevel")
    return Path(output).resolve() if output else None


def _worktree_root() -> Path:
    raw = os.getenv("ARTISAN_WORKTREE_ROOT")
    if raw:
        return Path(raw).expanduser()
    return workspace_dir("artifacts", create=True) / "artisan_worktrees"


def _dirty_summary(repo: Path) -> str:
    output = _git_output(repo, "status", "--short")
    if not output:
        return "clean"
    lines = output.splitlines()
    shown = "; ".join(lines[:8])
    if len(lines) > 8:
        shown += f"; +{len(lines) - 8} more"
    return shown


def _git_output(repo: Path, *args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (subprocess.CalledProcessError, OSError):
        return ""
    return proc.stdout.strip()
