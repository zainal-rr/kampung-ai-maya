from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from maya_core.execution_broker import CommandSpec, run_command
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
    result = run_command(CommandSpec(
        argv=("git", "-C", str(repo), "worktree", "add", "--detach", str(worktree), "HEAD"),
        cwd=repo,
        profile="workspace_write",
        write_roots=(repo, worktree.parent),
        timeout=60,
        text=True,
    ))
    if result.returncode != 0:
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
    result = run_command(CommandSpec(
        argv=("git", "-C", str(repo), *args),
        cwd=repo,
        profile="readonly",
        timeout=30,
        text=True,
    ))
    if result.returncode != 0:
        return ""
    return str(result.stdout).strip()
