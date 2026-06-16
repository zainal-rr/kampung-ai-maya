from __future__ import annotations

from approval_inbox import approval_items
from harness_artifact_store import latest_artifacts
from harness_store import list_active_runs
from project_store import active_project, project_notes
from storage import list_tasks
from waiting_on import list_waiting_on
from workflow_desk import is_quiet_mode


BUCKETS = {
    "health": ("health", "doctor", "fitness", "sleep", "medicine"),
    "money": ("money", "budget", "cost", "bank", "bill", "payment"),
    "family": ("family", "home", "parent", "wife", "child"),
    "work": ("work", "client", "meeting", "office", "job"),
    "learning": ("learn", "study", "course", "read", "research"),
    "Kampung AI": ("kampung", "maya", "api key", "mudra", "omi"),
}


async def daily_cockpit_text(db_path: str, channel: str) -> str:
    tasks = _unique_tasks([
        task for task in await list_tasks(db_path, limit=20)
        if task["action_type"] != "waiting_on"
    ])
    waiting = await list_waiting_on(db_path, limit=10)
    approvals = await approval_items(db_path)
    runs = await list_active_runs(db_path, limit=5)
    artifacts = await latest_artifacts(db_path, limit=3)
    project = await active_project(db_path)
    quiet = await is_quiet_mode(db_path)
    lines = []
    if tasks:
        lines.append("Tasks: " + ", ".join(str(item["title"]) for item in tasks[:3]))
    if waiting:
        lines.append("Waiting on: " + ", ".join(str(item["title"]) for item in waiting[:3]))
    if approvals:
        lines.append(f"Approvals: {len(approvals)} waiting.")
    if runs:
        lines.append("Workflows: " + ", ".join(str(run["workflow_type"]) for run in runs[:3]))
    if project:
        lines.append(f"Project: {project.name}")
    if artifacts:
        lines.append(f"Latest file: {artifacts[0].get('path') or artifacts[0].get('url')}")
    if quiet:
        lines.append("Quiet mode is on.")
    if not lines:
        lines.append("Nothing urgent is queued right now.")
    if channel == "imac":
        return "Today looks like this. " + " ".join(lines[:3])
    return "Today looks like this:\n" + "\n".join(f"{index + 1}) {line}" for index, line in enumerate(lines[:6]))


async def focus_text(db_path: str) -> str:
    tasks = await list_tasks(db_path, limit=10)
    waiting = await list_waiting_on(db_path, limit=10)
    candidates = _unique_tasks([
        task for task in tasks if task["action_type"] != "waiting_on"
    ])[:3]
    if candidates:
        lines = ["I would focus here first:"]
        for index, task in enumerate(candidates, start=1):
            bucket = bucket_for(f"{task['title']} {task['details']}")
            lines.append(f"{index}) {task['title']} ({bucket})")
        return "\n".join(lines)
    if waiting:
        return "Main blocker: " + ", ".join(str(item["title"]) for item in waiting[:3])
    return "Nothing urgent is queued. Pick one small useful thing and I will help you move it."


async def project_cockpit_text(db_path: str) -> str:
    project = await active_project(db_path)
    if not project:
        return "No active project yet. Open a project first and I can show its cockpit."
    notes = await project_notes(db_path, project.path, limit=4)
    artifacts = await latest_artifacts(db_path, limit=5)
    project_files = [item for item in artifacts if project.name.lower() in (item.get("path") or "").lower()]
    lines = [f"Project cockpit: {project.name}", f"Path: {project.path}"]
    if notes:
        lines.append("Recent memory: " + "; ".join(f"{item['kind']}: {item['content']}" for item in notes[:2]))
    if project_files:
        lines.append("Recent artifacts: " + ", ".join(str(item["path"]) for item in project_files[:2]))
    lines.append("Next step: tell me what you want to make, inspect, or clean up in this project.")
    return "\n".join(f"{index + 1}) {line}" for index, line in enumerate(lines))


def bucket_for(text: str) -> str:
    lowered = text.lower()
    for bucket, markers in BUCKETS.items():
        if any(marker in lowered for marker in markers):
            return bucket
    return "work"


def _unique_tasks(tasks: list[dict[str, str | int | None]]) -> list[dict[str, str | int | None]]:
    seen = set()
    unique = []
    for task in tasks:
        key = (str(task["title"]).strip().lower(), str(task.get("action_type") or ""))
        if key in seen:
            continue
        seen.add(key)
        unique.append(task)
    return unique
