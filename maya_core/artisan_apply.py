from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from maya_harness.harness_store import init_harness_db, record_event, upsert_run
from maya_core.execution_broker import CommandSpec, run_command
from maya_core.workspace_paths import workspace_dir


async def apply_latest_artisan_repo_changes(db_path: str, run_id: str | None = None) -> str:
    row = await _approved_repo_run(db_path, run_id)
    if not row:
        return "No approved Artisan repo changes are waiting to apply."
    state = json.loads(str(row["state_json"] or "{}"))
    worktree = Path(str(state.get("working_directory") or "")).expanduser()
    original = Path(str(state.get("original_repo_path") or "")).expanduser()
    selected_run_id = str(row["run_id"])
    if not worktree.exists() or not original.exists():
        return "I could not apply the Artisan changes because the worktree or original repo path is missing."
    if state.get("isolation_mode") != "git_worktree":
        return "I can only apply Artisan repo changes from an isolated git worktree."

    diff = _git_bytes(worktree, "diff", "--binary", "HEAD")
    if not diff.strip():
        await record_event(db_path, selected_run_id, "artisan_apply_noop", "No diff found in isolated worktree.")
        return "No changes found in the approved Artisan worktree."

    patch_path = _patch_path(selected_run_id)
    patch_path.write_bytes(diff)
    check = _git_apply(original, diff, "--check")
    if check.returncode != 0:
        await record_event(db_path, selected_run_id, "artisan_apply_failed", (check.stderr or check.stdout).decode("utf-8", "replace")[:1000])
        return (
            "I did not apply the Artisan changes because the patch no longer applies cleanly.\n"
            f"Patch saved for review: {patch_path}"
        )

    apply = _git_apply(original, diff)
    if apply.returncode != 0:
        await record_event(db_path, selected_run_id, "artisan_apply_failed", (apply.stderr or apply.stdout).decode("utf-8", "replace")[:1000])
        return (
            "I tried to apply the Artisan changes, but git apply failed.\n"
            f"Patch saved for review: {patch_path}"
        )

    state["apply_status"] = "applied_to_original_repo"
    state["applied_at"] = datetime.now(timezone.utc).isoformat()
    state["patch_path"] = str(patch_path)
    await upsert_run(db_path, state, status="completed")
    await record_event(db_path, selected_run_id, "artisan_applied_to_original_repo", f"Patch applied to {original}. Patch: {patch_path}")
    return (
        "Applied the approved Artisan repo changes to the original repo working tree.\n"
        f"1) run: {selected_run_id}\n"
        f"2) original repo: {original}\n"
        f"3) patch record: {patch_path}\n"
        "4) commit: not created"
    )


async def _approved_repo_run(db_path: str, run_id: str | None):
    await init_harness_db(db_path)
    params: tuple[str, ...]
    where = "workflow_type = 'artisan_repo' AND status = 'approved_waiting_manual_apply'"
    if run_id:
        where += " AND run_id = ?"
        params = (run_id,)
    else:
        params = ()
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""
            SELECT run_id, state_json, updated_at
            FROM harness_runs
            WHERE {where}
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            params,
        )
        return await cursor.fetchone()


def _git_bytes(cwd: Path, *args: str) -> bytes:
    result = run_command(CommandSpec(
        argv=("git", "-C", str(cwd), *args),
        cwd=cwd,
        profile="readonly",
        timeout=60,
        check=True,
    ))
    return bytes(result.stdout)


def _git_apply(cwd: Path, diff: bytes, *args: str):
    return run_command(CommandSpec(
        argv=("git", "-C", str(cwd), "apply", *args),
        cwd=cwd,
        profile="workspace_write",
        timeout=60,
        input_bytes=diff,
        write_roots=(cwd,),
    )).to_completed_process()


def _patch_path(run_id: str) -> Path:
    folder = workspace_dir("reports", create=True) / "artisan"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{run_id}.patch"
