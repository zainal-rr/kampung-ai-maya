from __future__ import annotations

from artisan_runner_context import *
from artisan_runner_postprocess import _compact


async def latest_artisan_summary_text(db_path: str) -> str:
    row = await _latest_artisan_run(db_path)
    if not row:
        return "No Artisan runs recorded yet."
    state = json.loads(str(row["state_json"] or "{}"))
    lines = [
        "Last Artisan run:",
        f"1) job: {row['run_id']}",
        f"2) status: {row['status']}",
        f"3) type: {row['workflow_type']}",
        f"4) path: {state.get('working_directory', '')}",
        f"5) summary: {state.get('summary') or state.get('status_note', '')}",
    ]
    changed = state.get("changed_files") or []
    if changed:
        lines.append("6) files: " + ", ".join(changed[:8]))
    return "\n".join(lines)


async def latest_artisan_transcript_text(db_path: str) -> str:
    row = await _latest_artisan_run(db_path)
    if not row:
        return "No Artisan transcript recorded yet."
    state = json.loads(str(row["state_json"] or "{}"))
    transcript = state.get("transcript_path") or ""
    if not transcript:
        return "The last Artisan run did not store a transcript path."
    return f"Last Artisan transcript: {transcript}"


async def latest_artisan_delivery_text(db_path: str, artifact_type: str, channel: str) -> str:
    normalized = artifact_type.lower().strip()
    workflow_type = "artisan_3d" if normalized in {"3d", "maker", "model"} else "artisan_app"
    row = await _latest_artisan_run(db_path, workflow_type=workflow_type)
    if not row:
        return f"I do not have a recent {'3D model' if workflow_type == 'artisan_3d' else 'app'} from Artisan yet."
    state = json.loads(str(row["state_json"] or "{}"))
    if workflow_type == "artisan_app":
        return _latest_app_delivery_text(state, channel)
    return _latest_maker_delivery_text(state, channel)


def _latest_app_delivery_text(state: dict, channel: str) -> str:
    qa = state.get("app_qa") or {}
    app_root = Path(str(qa.get("app_root") or state.get("working_directory") or "")).expanduser()
    summary = state.get("summary") or state.get("status_note") or "Artisan app project."
    exists = "yes" if app_root.exists() else "no"
    lines = [
        f"Last app: {app_root}",
        f"Exists on iMac: {exists}",
        f"Summary: {_compact(summary)}",
    ]
    if qa.get("preview_path"):
        lines.append(f"Preview: {qa['preview_path']}")
    if channel == "telegram" and app_root.exists():
        archive = _zip_directory(app_root, "app")
        if archive:
            lines.append(f"[file:{archive}]")
        preview = qa.get("preview_path") or ""
        if preview and Path(preview).exists():
            lines.append(f"[file:{preview}]")
    return "\n".join(lines)


def _latest_maker_delivery_text(state: dict, channel: str) -> str:
    qa = state.get("maker_qa") or {}
    root = Path(str(state.get("working_directory") or "")).expanduser()
    summary = state.get("summary") or state.get("status_note") or "Artisan maker output."
    exists = "yes" if root.exists() else "no"
    lines = [
        f"Last 3D model: {root}",
        f"Exists on iMac: {exists}",
        f"Summary: {_compact(summary)}",
        "Safety: not sliced, uploaded, or sent to a printer.",
    ]
    dimensions = qa.get("dimensions_mm") or {}
    if dimensions:
        first_name, first_dims = next(iter(dimensions.items()))
        lines.append(f"Dimensions: {first_name} = {first_dims[0]} x {first_dims[1]} x {first_dims[2]} mm")
    if channel == "telegram":
        for path in _maker_delivery_files(qa):
            lines.append(f"[file:{path}]")
    return "\n".join(lines)


def _maker_delivery_files(qa: dict) -> list[str]:
    files: list[str] = []
    for key in ("mesh_files", "blend_files", "readme_files", "preview_files"):
        for item in qa.get(key) or []:
            path = Path(str(item))
            if path.exists() and path.is_file():
                files.append(str(path))
    return files[:8]


def _zip_directory(root: Path, label: str) -> Path | None:
    if not root.exists() or not root.is_dir():
        return None
    folder = workspace_dir("reports", create=True) / "artisan-delivery"
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder / f"{safe_slug(root.name, 48)}-{label}.zip"
    ignored = {".git", "node_modules", "__pycache__"}
    with ZipFile(archive, "w", ZIP_DEFLATED) as zip_file:
        for path in root.rglob("*"):
            if not path.is_file() or any(part in ignored for part in path.parts):
                continue
            if path.name == ".DS_Store":
                continue
            zip_file.write(path, path.relative_to(root))
    return archive if archive.exists() and archive.stat().st_size > 100 else None


async def _latest_artisan_run(db_path: str, workflow_type: str | None = None):
    await init_harness_db(db_path)
    where = "workflow_type LIKE 'artisan%'"
    params: tuple[str | int, ...]
    if workflow_type:
        where = "workflow_type = ?"
        params = (workflow_type,)
    else:
        params = ()
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""
            SELECT run_id, workflow_type, status, state_json, updated_at
            FROM harness_runs
            WHERE {where}
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            params,
        )
        return await cursor.fetchone()


def _reply(run_id: str, target: ArtisanTarget, result: dict, changed_files: list[str]) -> str:
    lines = [
        "I moved this to Artisan.",
        f"1) job: {run_id}",
        f"2) type: {target.workflow_type}",
        f"3) path: {target.cwd}",
        f"4) status: {result['status_note']}",
        f"5) approval: {target.approval_state}",
    ]
    if target.original_repo_path:
        lines.append(f"6) original repo: {target.original_repo_path}")
        lines.append(f"7) isolation: {target.isolation_mode}")
    if changed_files:
        lines.append("8) files: " + ", ".join(changed_files[:6]))
    return "\n".join(lines)
