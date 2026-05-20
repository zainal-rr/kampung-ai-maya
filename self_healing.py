from __future__ import annotations

from pathlib import Path

from code_health import collect_code_health, format_code_health
from self_heal_store import create_self_heal_report, record_self_heal_stage
from storage import create_task
from storage_tasks import update_task_status


def detect_bug_signals(root: str | Path = ".") -> list[str]:
    root_path = Path(root)
    signals = []
    health = collect_code_health(root_path)
    if health.violations or health.urgent:
        signals.append(format_code_health(health))
    for name in ("logs/error.log", "logs/launchd.stderr.log"):
        path = root_path / name
        if not path.exists():
            continue
        tail = "\n".join(path.read_text(encoding="utf-8", errors="ignore").splitlines()[-40:])
        if any(marker in tail for marker in ("Traceback", "ERROR", "Exception", "failed")):
            signals.append(f"{name} has recent failure signals.")
    return signals


def isolate_subsystem(issue: str) -> str:
    lowered = issue.lower()
    if "telegram" in lowered:
        return "telegram channel or command routing"
    if "screen" in lowered or "vision" in lowered or "camera" in lowered:
        return "screen or vision subsystem"
    if "line" in lowered or "limit" in lowered:
        return "code organization and file-size health"
    if "traceback" in lowered or "error.log" in lowered:
        return "runtime error path from recent logs"
    return "unknown subsystem, needs reproduction before patching"


async def self_heal_text(db_path: str, root: str | Path = ".") -> str:
    signals = detect_bug_signals(root)
    if not signals:
        await record_self_heal_stage(db_path, None, "closed", "No clear bug signal detected.")
        return (
            "Self heal check:\n"
            "1) No repair proposal needed right now.\n"
            "2) Code health and recent logs do not show a clear bug signal."
        )
    issue = signals[0]
    subsystem = isolate_subsystem(issue)
    diagnosis = _diagnose(issue)
    proposed_fix = _propose_fix(issue)
    tests = "Reproduce if possible, run targeted smoke, code_health.py, then may1_rehearsal.py before restart."
    task_id = await create_task(
        db_path,
        title="Review Maya self-heal proposal",
        details=diagnosis,
        action_type="apply_code_patch",
        autonomy_mode="suggest",
    )
    await update_task_status(db_path, task_id, "awaiting_confirmation", result="Repair proposal awaiting review.")
    report_id = await create_self_heal_report(
        db_path,
        issue=issue,
        diagnosis=diagnosis,
        proposed_fix=proposed_fix,
        tests=tests,
        task_id=task_id,
    )
    await record_self_heal_stage(db_path, report_id, "detected", issue)
    await record_self_heal_stage(db_path, report_id, "isolated", subsystem)
    await record_self_heal_stage(db_path, report_id, "proposed", proposed_fix)
    return (
        "Self heal check:\n"
        f"1) Stage: proposal only. No code has been changed.\n"
        f"2) Detected: {issue}\n"
        f"3) Likely subsystem: {subsystem}\n"
        f"4) Diagnosis: {diagnosis}\n"
        f"5) Proposed smallest patch direction: {proposed_fix}\n"
        f"6) Test plan: {tests}\n"
        f"7) Created repair proposal #{report_id} and review task #{task_id}. I will ask before patch, deploy, or restart."
    )


def _diagnose(issue: str) -> str:
    if "line" in issue.lower() or "limit" in issue.lower():
        return "A file-size or code-health rule needs attention before it becomes hard to maintain."
    return "Recent runtime logs show a failure signal that should be isolated before changing code."


def _propose_fix(issue: str) -> str:
    if "line" in issue.lower() or "limit" in issue.lower():
        return "Extract a focused module, keep behavior unchanged, then run code health and affected smokes."
    return "Reproduce the failing path, patch the smallest module, run targeted tests, then restart only after approval."
