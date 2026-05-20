from __future__ import annotations

from harness_artifact_store import latest_artifacts
from harness_checkpoint_reader import snapshot_for_run
from harness_store import latest_events, list_active_runs


async def build_resume_summary(db_path: str, channel: str) -> str:
    runs = await list_active_runs(db_path, channel)
    if not runs:
        return "No active workflow right now."
    if len(runs) > 1:
        lines = [f"{idx}) {run['workflow_type']}: {run['goal']}" for idx, run in enumerate(runs, start=1)]
        return "I have more than one workflow open. Which one should I continue?\n" + "\n".join(lines)
    run = runs[0]
    state = await snapshot_for_run(db_path, run)
    events = await latest_events(db_path, run["run_id"], limit=4)
    artifacts = await latest_artifacts(db_path, run["run_id"], limit=3)
    lines = [
        f"Workflow: {run['workflow_type']}",
        f"Goal: {run['goal']}",
        f"Status: {run['status']}",
        f"Last step: {state.get('last_successful_step') or _last_event(events)}",
        f"Next: {state.get('next_suggested_step') or 'continue from the last safe step'}",
    ]
    pending = state.get("pending_approval") or {}
    if pending:
        lines.append(f"Pending approval: {pending.get('details') or pending.get('action')}")
    if artifacts:
        lines.append("Artifacts: " + ", ".join(_artifact_label(item) for item in artifacts))
    return "\n".join(lines)


def _last_event(events: list[dict[str, str]]) -> str:
    return events[-1]["event"] if events else "not started"


def _artifact_label(item: dict[str, str]) -> str:
    return item.get("path") or item.get("url") or item.get("summary") or item.get("kind") or "artifact"
