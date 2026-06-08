from __future__ import annotations

from artisan_runner_context import *
from artisan_runner_delivery import (
    _reply,
    latest_artisan_delivery_text,
    latest_artisan_summary_text,
    latest_artisan_transcript_text,
)
from artisan_runner_engine import (
    _blender_available,
    _codex_chatgpt_auth_state,
    _repo_approval_details,
    _run_artisan_engine,
    _run_maker_template_source,
)
from artisan_runner_models import ArtisanTarget
from artisan_runner_postprocess import _file_snapshot, _post_process_artisan_output, _record_artifacts
from artisan_runner_targeting import _initial_state, _target_for_request, classify_artisan_request


async def create_artisan_implementation_request(
    db_path: str | None,
    request: str,
    channel: str,
    *,
    gemini_build_brief: str,
) -> tuple[str, str]:
    if not gemini_build_brief.strip():
        raise ValueError("Artisan requires a Gemini-created build brief.")
    run_id = new_run_id()
    target = await _target_for_request(db_path, request, run_id)
    target.cwd.mkdir(parents=True, exist_ok=True)
    before = _file_snapshot(target.cwd)
    state = _initial_state(run_id, channel, request, target, gemini_build_brief)
    maker_template_plan = select_maker_template(request, gemini_build_brief) if target.workflow_type == "artisan_3d" else None
    if maker_template_plan:
        state["maker_template"] = maker_template_plan.as_dict()
        state["agents"] = ["gemini_build_brief", "maya_maker_template", "maya_blender_export_qa"]
        state["status_note"] = "running deterministic Maya maker template"
    if db_path:
        await upsert_run(db_path, state, status="running")
        await record_event(db_path, run_id, "gemini_build_brief_created", gemini_build_brief[:1000])
        await record_event(db_path, run_id, "artisan_started", f"{target.workflow_type} in {target.cwd}")
        if maker_template_plan:
            await record_event(db_path, run_id, "maker_template_selected", json.dumps(maker_template_plan.as_dict(), ensure_ascii=False)[:1000])
    result = (
        await _run_maker_template_source(run_id, target, maker_template_plan)
        if maker_template_plan
        else await _run_artisan_engine(run_id, request, target, gemini_build_brief)
    )
    after = _file_snapshot(target.cwd)
    changed_files = sorted(after - before)[:80]
    post_checks = await _post_process_artisan_output(target, request, gemini_build_brief, result, changed_files)
    after = _file_snapshot(target.cwd)
    changed_files = sorted(after - before)[:80]
    state.update(
        {
            "status_note": result["status_note"],
            "artisan_session_id": result.get("session_id", ""),
            "summary": result["summary"][:2000],
            "changed_files": changed_files,
            "tests_run": result.get("tests_run", []),
            "transcript_path": result.get("transcript_path", ""),
            "approval_state": target.approval_state,
            "blender_available": _blender_available(),
            "original_repo_path": str(target.original_repo_path or ""),
            "isolation_mode": target.isolation_mode,
            "base_ref": target.base_ref,
            "dirty_summary": target.dirty_summary,
            "apply_requires_approval": target.approval_state == "repo_approval_required",
            **post_checks,
        }
    )
    status = "paused" if target.approval_state == "repo_approval_required" else result["status"]
    if db_path:
        await upsert_run(db_path, state, status=status)
        await record_event(db_path, run_id, "artisan_finished", result["summary"][:1000])
        if not maker_template_plan:
            await record_usage(db_path, "codex_implementation_jobs", 1, "Artisan Codex job")
        await _record_artifacts(db_path, run_id, target, changed_files, result)
        if target.approval_state == "repo_approval_required":
            await create_approval(
                db_path,
                run_id,
                "apply_artisan_repo_changes",
                _repo_approval_details(target, changed_files),
            )
        if target.project_slug:
            await remember_project_note(db_path, target.cwd, "artisan", result["summary"][:500])
        if status == "completed" and target.workflow_type == "artisan_app":
            app_root = str((state.get("app_qa") or {}).get("app_root") or target.cwd)
            await upsert_preference(db_path, "maya_last_app_project_path", app_root, "artisan")
        if status == "completed" and target.workflow_type == "artisan_3d":
            await upsert_preference(db_path, "maya_last_maker_project_path", str(target.cwd), "artisan")
    return run_id, _reply(run_id, target, result, changed_files)


__all__ = [
    "ArtisanTarget",
    "_codex_chatgpt_auth_state",
    "classify_artisan_request",
    "create_artisan_implementation_request",
    "latest_artisan_delivery_text",
    "latest_artisan_summary_text",
    "latest_artisan_transcript_text",
]
