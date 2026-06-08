from __future__ import annotations

from artisan_runner_context import *


async def _target_for_request(db_path: str | None, request: str, run_id: str) -> ArtisanTarget:
    kind = classify_artisan_request(request)
    project = await active_project(db_path) if db_path else None
    if kind in {"artisan_app", "artisan_3d"}:
        latest_path = await _latest_target_path(db_path, kind, request)
        if latest_path and is_workspace_path(latest_path):
            return ArtisanTarget(kind, latest_path, "acceptEdits", "direct_workspace", latest_path.name)
        slug = safe_slug(_project_title(request), 48)
        root = workspace_dir("Projects", create=True)
        cwd = project.path if project and is_workspace_path(project.path) else root / slug
        subdir = cwd / "3d" if kind == "artisan_3d" else cwd
        return ArtisanTarget(kind, subdir, "acceptEdits", "direct_workspace", slug)
    if project and is_workspace_path(project.path):
        return ArtisanTarget("artisan_project_code", project.path, "acceptEdits", "direct_workspace", project.name)
    isolation = create_repo_isolation(Path.cwd(), run_id)
    if isolation:
        return ArtisanTarget(
            "artisan_repo",
            isolation.worktree_path,
            "acceptEdits",
            "repo_approval_required",
            original_repo_path=isolation.original_repo,
            isolation_mode="git_worktree",
            base_ref=isolation.base_ref,
            dirty_summary=isolation.dirty_summary,
        )
    return ArtisanTarget(
        "artisan_repo",
        Path.cwd(),
        "plan",
        "repo_approval_required",
        original_repo_path=Path.cwd(),
        isolation_mode="plan_only_no_worktree",
    )


async def _latest_target_path(db_path: str | None, kind: str, request: str) -> Path | None:
    if not db_path or not _is_edit_followup(request):
        return None
    key = "maya_last_maker_project_path" if kind == "artisan_3d" else "maya_last_app_project_path"
    value = await get_preference(db_path, key)
    if not value:
        return None
    path = Path(value).expanduser()
    return path if path.exists() else None


def _is_edit_followup(text: str) -> bool:
    lowered = text.lower().strip()
    return any(
        marker in lowered
        for marker in (
            "edit the last", "edit last", "update the last", "update last", "change the last",
            "change last", "modify the last", "modify last", "edit that", "update that",
            "change that", "make it", "make the last", "wider", "dark mode",
        )
    )


def classify_artisan_request(text: str) -> str:
    lowered = text.lower()
    if any(marker in lowered for marker in ("blender", "3d print", "3d-print", "stl", "3mf", "phone stand", "printable", "3d model", "wall hook", "key tag", "label tag", "organizer tray")):
        return "artisan_3d"
    if any(marker in lowered for marker in (" app", "web app", "website", "frontend", "react", "vite", "dashboard", "ui", "last app")):
        return "artisan_app"
    return "artisan_repo"


def _project_title(text: str) -> str:
    cleaned = re.sub(
        r"\b(make|create|build|generate|code|me|a|an|the|simple|for|in|with|using)\b",
        " ",
        text,
        flags=re.I,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned or "maya-project"


def _initial_state(
    run_id: str,
    channel: str,
    request: str,
    target: ArtisanTarget,
    gemini_build_brief: str,
) -> dict:
    return {
        "run_id": run_id,
        "thread_id": "maya:artisan",
        "channel": channel,
        "workflow_type": target.workflow_type,
        "goal": request[:500],
        "current_step": 1,
        "agents": ["gemini_build_brief", "artisan_codex"],
        "owner_lane": "Artisan",
        "status_note": "running Artisan through Codex",
        "working_directory": str(target.cwd),
        "permission_mode": target.permission_mode,
        "approval_state": target.approval_state,
        "original_repo_path": str(target.original_repo_path or ""),
        "isolation_mode": target.isolation_mode,
        "base_ref": target.base_ref,
        "dirty_summary": target.dirty_summary,
        "gemini_build_brief": gemini_build_brief[:4000],
    }
