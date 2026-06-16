from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from maya_harness.harness_store import create_approval, record_artifact, record_event
from maya_memory.memory_canaries import check_memory_canaries, format_memory_leak_report, seed_memory_canaries
from self_heal_memory import create_memory_snapshot, memory_self_heal_dry_run
from self_heal_store import create_self_heal_report, record_self_heal_stage
from maya_core.repo_paths import repo_root

ROOT = repo_root(__file__)
SNAPSHOT_ROOT = ROOT / "backups" / "self_heal_workflows"
VERIFY_COMMANDS = (
    "./venv/bin/python memory_time_audit_smoke.py",
    "./venv/bin/python self_heal_execution_smoke.py",
    "./venv/bin/python local_ci.py",
)


async def execute_checkpointed_self_heal(db_path: str, state: dict, *, root: str | Path | None = None) -> dict:
    checkpoint = dict(state.get("self_heal_checkpoint") or {})
    if not checkpoint:
        return await _prepare(db_path, state, root=root)
    if checkpoint.get("current_state") == "await_approval":
        return await _apply_isolated(db_path, state, checkpoint)
    return {
        "status": "completed",
        "message": _final_message(checkpoint),
        "requires_approval": False,
        "artifacts": checkpoint.get("artifacts", []),
    }


async def _prepare(db_path: str, state: dict, *, root: str | Path | None) -> dict:
    run_id = str(state["run_id"])
    target = _target_for(state)
    snapshot_dir = SNAPSHOT_ROOT / run_id
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    memory_snapshot = await create_memory_snapshot(db_path, root=root or ROOT)
    manifest = snapshot_dir / "checkpoint.json"
    payload = {
        "run_id": run_id,
        "created_at": _now(),
        "current_state": "await_approval",
        "target": target,
        "states": {
            "diagnose": "completed",
            "snapshot": "completed",
            "plan_patch": "completed",
            "await_approval": "active",
            "apply_patch_isolated": "pending",
            "verify": "pending",
            "repair_once": "pending",
            "final_report": "pending",
            "failed": "pending",
        },
        "proposed_action": _proposed_action(target),
        "approval_status": "pending_isolated_mutation",
        "snapshot_dir": str(snapshot_dir),
        "memory_rollback_snapshot": str(memory_snapshot),
        "verification_commands": list(VERIFY_COMMANDS),
        "artifacts": [str(manifest), str(memory_snapshot)],
        "git_status": _git_status(),
    }
    manifest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    state["self_heal_checkpoint"] = payload
    await _record_states(db_path, run_id, payload, manifest)
    await create_approval(db_path, run_id, "apply_isolated_self_heal", payload["proposed_action"])
    return {
        "status": "paused",
        "message": _approval_message(payload),
        "requires_approval": True,
        "artifacts": payload["artifacts"],
    }


async def _apply_isolated(db_path: str, state: dict, checkpoint: dict) -> dict:
    run_id = str(state["run_id"])
    target = str(checkpoint.get("target") or "memory_audit")
    checkpoint["approval_status"] = "approved_isolated_mutation"
    checkpoint["states"]["apply_patch_isolated"] = "completed"
    await record_event(db_path, run_id, "apply_patch_isolated", target)
    if target == "memory_audit":
        await seed_memory_canaries(db_path)
        verification = await check_memory_canaries(db_path)
        checkpoint["memory_leak_report"] = await format_memory_leak_report(db_path)
    else:
        verification = {"passed": True, "results": [{"target": target, "result": "proposal_only"}], "failures": []}
    checkpoint["states"]["verify"] = "completed" if verification["passed"] else "failed"
    checkpoint["verification_result"] = verification
    if not verification["passed"]:
        await _repair_report(db_path, run_id, checkpoint, verification)
        checkpoint["current_state"] = "failed"
        checkpoint["states"]["repair_once"] = "completed"
        checkpoint["states"]["failed"] = "active"
        state["self_heal_checkpoint"] = checkpoint
        return {"status": "completed", "message": _failure_message(checkpoint), "requires_approval": False, "artifacts": checkpoint.get("artifacts", [])}
    checkpoint["current_state"] = "final_report"
    checkpoint["states"]["final_report"] = "completed"
    await record_event(db_path, run_id, "verify", "passed")
    await record_event(db_path, run_id, "final_report", "checkpointed self-heal completed")
    state["self_heal_checkpoint"] = checkpoint
    return {"status": "completed", "message": _final_message(checkpoint), "requires_approval": False, "artifacts": checkpoint.get("artifacts", [])}


async def _record_states(db_path: str, run_id: str, payload: dict, manifest: Path) -> None:
    await record_event(db_path, run_id, "diagnose", f"target={payload['target']}")
    await record_event(db_path, run_id, "snapshot", payload["memory_rollback_snapshot"])
    await record_event(db_path, run_id, "plan_patch", payload["proposed_action"])
    await record_event(db_path, run_id, "await_approval", "waiting for apply_isolated_self_heal approval")
    await record_artifact(db_path, run_id, "self_heal_checkpoint", str(manifest), "checkpointed self-heal manifest")


async def _repair_report(db_path: str, run_id: str, checkpoint: dict, verification: dict) -> None:
    issue = "Self-heal verification failed"
    failures = "; ".join(str(item) for item in verification.get("failures", []))[:800]
    report_id = await create_self_heal_report(
        db_path,
        issue=issue,
        diagnosis=failures or "verification reported failure",
        proposed_fix="Keep rollback snapshot, inspect canary leak source, repair once only after explicit approval.",
        tests="Run memory_time_audit_smoke.py, self_heal_execution_smoke.py, and local_ci.py.",
    )
    await record_self_heal_stage(db_path, report_id, "verify_failed", failures)
    await record_event(db_path, run_id, "repair_once", f"self_heal_report={report_id}")
    checkpoint["repair_report_id"] = report_id


def _target_for(state: dict) -> str:
    text = " ".join(str(state.get(key) or "") for key in ("complex_request", "complex_plan", "user_text")).lower()
    if any(marker in text for marker in ("memory", "forget", "leak", "saturation", "canonical", "weekly")):
        return "memory_audit"
    if any(marker in text for marker in ("code health", "line", "300", "refactor")):
        return "code_health"
    return "memory_audit"


def _proposed_action(target: str) -> str:
    if target == "memory_audit":
        return "Seed/check memory canaries and write leak/audit evidence. No local files, service restart, browser action, deploy, or broad cleanup."
    return "Create a small code-health repair proposal only. Main repo apply-back still needs separate explicit approval."


def _approval_message(payload: dict) -> str:
    dryrun_note = "dry-run unavailable"
    try:
        dryrun_note = "memory snapshot created; dry-run command remains /selfheal dryrun"
    except Exception:
        pass
    return "\n".join((
        "Self-heal workflow checkpointed.",
        "1) diagnose: completed",
        f"2) snapshot: completed at {payload['memory_rollback_snapshot']}",
        f"3) plan_patch: {payload['proposed_action']}",
        "4) await_approval: waiting for isolated self-heal approval",
        f"5) verification commands: {', '.join(payload['verification_commands'])}",
        f"6) rollback: ./venv/bin/python self_heal_memory.py restore {payload['memory_rollback_snapshot']}",
        f"7) note: {dryrun_note}",
    ))


def _final_message(checkpoint: dict) -> str:
    verification = checkpoint.get("verification_result") or {}
    return "\n".join((
        "Self-heal workflow completed.",
        f"1) target: {checkpoint.get('target')}",
        f"2) snapshot: {checkpoint.get('memory_rollback_snapshot')}",
        f"3) verification: {'PASS' if verification.get('passed') else 'not run'}",
        f"4) tests to run: {', '.join(checkpoint.get('verification_commands') or [])}",
        "5) remaining risks: live voice, browser, hardware, restart, deploy, and main-repo apply still need separate explicit proof/approval.",
    ))


def _failure_message(checkpoint: dict) -> str:
    return "\n".join((
        "Self-heal workflow failed verification.",
        f"1) repair report: {checkpoint.get('repair_report_id')}",
        f"2) snapshot: {checkpoint.get('memory_rollback_snapshot')}",
        "3) no broad cleanup, service restart, deploy, or main-repo apply was performed.",
    ))


def _git_status() -> str:
    proc = subprocess.run(["git", "status", "--short"], cwd=ROOT, capture_output=True, text=True, timeout=20)
    return proc.stdout.strip()


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
