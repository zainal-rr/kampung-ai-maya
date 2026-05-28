from __future__ import annotations


async def read_maya_state(db_path: str, question: str) -> str:
    lowered = question.lower()
    if "approval" in lowered or "approve" in lowered:
        from approval_inbox import approval_inbox_text
        return await approval_inbox_text(db_path)
    if "artifact" in lowered or "file" in lowered or "created" in lowered:
        return await _artifact_text(db_path)
    if "task" in lowered:
        return await _task_text(db_path)
    if "project" in lowered:
        from daily_cockpit import project_cockpit_text
        return await project_cockpit_text(db_path)
    if "focus" in lowered:
        from daily_cockpit import focus_text
        return await focus_text(db_path)
    if "today" in lowered or "morning" in lowered:
        from daily_cockpit import daily_cockpit_text
        return await daily_cockpit_text(db_path, "imac")
    if "cost" in lowered or "usage" in lowered:
        from cost_tracker import usage_summary_text
        return await usage_summary_text(db_path)
    if "route" in lowered:
        from route_tracker import last_route_text
        return await last_route_text(db_path)
    from telegram_status import status_text
    return await status_text(db_path)


async def _artifact_text(db_path: str) -> str:
    from harness_artifact_store import latest_artifacts

    artifacts = await latest_artifacts(db_path, limit=8)
    if not artifacts:
        return "No artifacts recorded yet."
    lines = ["Latest artifacts:"]
    for index, item in enumerate(artifacts, start=1):
        lines.append(f"{index}) {item.get('kind')}: {item.get('path') or item.get('url')}")
    return "\n".join(lines)


async def _task_text(db_path: str) -> str:
    from assistant_task_helpers import format_open_tasks
    from storage import list_tasks

    return format_open_tasks(await list_tasks(db_path, limit=8))
