from __future__ import annotations

from maya_harness.harness_artifact_store import latest_artifacts
from maya_harness.harness_store import finish_run, list_active_runs
from maya_core.project_store import active_project
from maya_core.retention_policy import retention_status_summary
from maya_core.storage import get_preference, upsert_preference


IMAC_BODY_WORKFLOWS = {"browser", "screen", "app"}
QUIET_MODE_KEY = "quiet_mode"


async def workflow_desk_text(db_path: str) -> str:
    runs = await list_active_runs(db_path, limit=8)
    artifacts = await latest_artifacts(db_path, limit=5)
    project = await active_project(db_path)
    lines = ["Workflow desk:"]
    if project:
        lines.append(f"1) Active project: {project.name}")
    if not runs:
        lines.append("1) No active workflows right now." if not project else "2) No active workflows right now.")
    else:
        for index, run in enumerate(runs, start=1 if not project else 2):
            lines.append(f"{index}) {run['workflow_type']}: {run['goal']} ({run['status']})")
    if artifacts:
        latest = artifacts[0]
        lines.append(f"{len(lines)}) Latest artifact: {latest.get('path') or latest.get('url')}")
    retention = await retention_status_summary(db_path)
    if "pending" in retention.lower() and "no project/task" not in retention.lower():
        lines.append(f"{len(lines)}) {retention}")
    return "\n".join(lines)


async def background_tasks_text(db_path: str) -> str:
    runs = await list_active_runs(db_path, limit=10)
    if not runs:
        return "No background workflows are running right now."
    lines = ["Background workflows:"]
    for index, run in enumerate(runs, start=1):
        lines.append(f"{index}) {run['workflow_type']}: {run['goal']} ({run['status']})")
    return "\n".join(lines)


async def close_matching_workflow(db_path: str, query: str) -> str:
    runs = await list_active_runs(db_path, limit=20)
    matches = [run for run in runs if _matches(run, query)]
    if not matches:
        return "I could not find an active workflow matching that."
    for run in matches:
        await finish_run(db_path, str(run["run_id"]), status="cancelled")
    if len(matches) == 1:
        return f"Okay. I closed the {matches[0]['workflow_type']} workflow."
    return f"Okay. I closed {len(matches)} workflows."


async def quiet_mode_text(db_path: str, text: str) -> str | None:
    cleaned = " ".join(text.lower().split())
    if cleaned == "quiet mode on":
        await upsert_preference(db_path, QUIET_MODE_KEY, "on", source="quiet_mode")
        return "Quiet mode is on."
    if cleaned == "quiet mode off":
        await upsert_preference(db_path, QUIET_MODE_KEY, "off", source="quiet_mode")
        return "Quiet mode is off."
    if cleaned == "am i in quiet mode":
        enabled = await is_quiet_mode(db_path)
        return "Quiet mode is on." if enabled else "Quiet mode is off."
    return None


async def is_quiet_mode(db_path: str) -> bool:
    return (await get_preference(db_path, QUIET_MODE_KEY) or "").lower() == "on"


def _matches(run: dict, query: str) -> bool:
    haystack = f"{run['workflow_type']} {run['goal']}".lower()
    tokens = [token for token in query.lower().split() if len(token) > 2]
    return bool(tokens) and all(token in haystack for token in tokens)
