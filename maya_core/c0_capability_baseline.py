from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import re
import shutil
import tempfile
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from maya_core.c0_capability_manifest import build_maya_domain_capability_manifest
from maya_core.c0_capability_models import (
    ALLOWED_REASON_CODES,
    CapabilityManifest,
    CapabilityOracle,
    CapabilityReport,
    CapabilityTask,
    CapabilityTaskResult,
    LlmCall,
    Outcome,
    ReasonCode,
    SemanticEvaluator,
)
from maya_core.c0_capability_providers import (
    build_openai_planner_llm,
    build_openai_semantic_evaluator,
    scripted_planner_llm,
)
from maya_core.maya_runtime_config import reload_runtime_config
from maya_core.storage import init_db
from maya_harness.harness_artifact_store import latest_artifacts
from maya_harness.harness_graph import HarnessGraphRunner
from maya_harness.harness_idempotency import init_action_ledger
from maya_harness.harness_state import initial_harness_state
from maya_harness.harness_store import init_harness_db, latest_events
from maya_harness.harness_workflows import classify_workflow

PathPattern = re.compile(r"(/[^\s\]]+\.(?:md|txt|docx|xlsx|pptx|html))")


async def run_capability_baseline(
    manifest: CapabilityManifest,
    *,
    planner_llm: LlmCall | None,
    semantic_evaluator: SemanticEvaluator | None = None,
    workspace_root: str | Path | None = None,
) -> tuple[tuple[CapabilityTaskResult, ...], str]:
    if planner_llm is None:
        raise ValueError("planner_llm is required for a real C0 baseline run")
    workspace_cm = tempfile.TemporaryDirectory(prefix="maya-c0-workspace-") if workspace_root is None else None
    workspace = Path(workspace_root or workspace_cm.name).expanduser()  # type: ignore[union-attr]
    workspace.mkdir(parents=True, exist_ok=True)
    previous = {key: os.environ.get(key) for key in ("MAYA_WORKSPACE_ROOT", "MAYA_TEST_MODE", "MAYA_AGENTIC_LOOP")}
    os.environ["MAYA_WORKSPACE_ROOT"] = str(workspace)
    os.environ["MAYA_TEST_MODE"] = "1"
    os.environ["MAYA_AGENTIC_LOOP"] = "1"
    reload_runtime_config()
    try:
        results = [await _run_task(task, planner_llm, semantic_evaluator, workspace) for task in manifest.tasks]
        return tuple(results), str(workspace)
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        reload_runtime_config()
        if workspace_cm is not None:
            workspace_cm.cleanup()


async def _run_task(
    task: CapabilityTask,
    planner_llm: LlmCall,
    semantic_evaluator: SemanticEvaluator | None,
    workspace: Path,
) -> CapabilityTaskResult:
    started = time.monotonic()
    db_path = str(workspace / f"{task.task_id}.db")
    await init_db(db_path)
    await init_harness_db(db_path)
    await init_action_ledger(db_path)
    state = initial_harness_state(
        run_id=f"c0_{task.task_id}",
        thread_id=f"harness:c0:{task.task_id}",
        channel="imac",
        user_text=task.prompt,
        workflow_type=task.workflow_type or classify_workflow(task.prompt),
    )
    state["agentic_loop"] = True
    state["max_steps"] = task.max_steps
    timed_out = False
    try:
        out = await asyncio.wait_for(HarnessGraphRunner(db_path, planner_llm=planner_llm).run(state), timeout=task.timeout_s)
    except asyncio.TimeoutError:
        timed_out = True
        out = {"final_response": f"I stopped because the C0 task timed out after {task.timeout_s}s.", "graph_status": "timeout"}
    except Exception as exc:  # noqa: BLE001 - report provider/tool failures instead of crashing the batch
        out = {"final_response": f"C0 provider/tool error: {type(exc).__name__}: {exc}", "graph_status": "error"}
    payload = {
        "state": out,
        "events": tuple(await latest_events(db_path, state["run_id"], limit=120)),
        "artifacts": tuple(await latest_artifacts(db_path, state["run_id"], limit=20)),
        "timed_out": timed_out,
    }
    outcome, oracle_status = await _score_outcome(task, payload, semantic_evaluator)
    reason_code, component = _trace_grounded_reason(task, payload, outcome)
    return CapabilityTaskResult(
        task.task_id,
        task.category,
        outcome,
        reason_code,
        component,
        task.oracle.oracle_type,
        oracle_status,
        str(out.get("final_response") or ""),
        str(out.get("graph_status") or ""),
        events=payload["events"],
        artifacts=payload["artifacts"],
        elapsed_s=round(time.monotonic() - started, 3),
        timed_out=timed_out,
    )


async def _score_outcome(
    task: CapabilityTask,
    payload: dict[str, Any],
    semantic_evaluator: SemanticEvaluator | None,
) -> tuple[Outcome, str]:
    final = str(payload["state"].get("final_response") or "")
    lowered = final.lower()
    if task.oracle.oracle_type == "artifact":
        if _has_existing_artifact(payload):
            return "success", "deterministic_artifact_exists"
        if payload.get("timed_out"):
            return "fail", "deterministic_artifact_timeout"
        if _looks_like_honest_stop(lowered):
            return "partial", "deterministic_artifact_not_created_honest_stop"
        return "fail", "deterministic_artifact_missing"
    if task.oracle.oracle_type in {"honest_stop", "approval_required"}:
        if payload["state"].get("pending_approval") or str(payload["state"].get("graph_status") or "") == "waiting_approval":
            return "honest_stop", "deterministic_waiting_approval"
        return ("honest_stop", "deterministic_honest_stop") if _looks_like_honest_stop(lowered) else ("fail", "deterministic_expected_stop_missing")
    if _looks_like_honest_stop(lowered) and task.oracle.allows_honest_stop:
        return "honest_stop", "deterministic_honest_gap"
    if semantic_evaluator is None:
        return "partial", "semantic_review_required"
    verdict = await semantic_evaluator(final, task, payload)
    outcome = str(verdict.get("outcome") or "partial")
    if outcome not in {"success", "partial", "fail", "honest_stop"}:
        outcome = "partial"
    if outcome == "honest_stop" and not task.oracle.allows_honest_stop:
        outcome = "fail"
    return outcome, f"semantic:{verdict.get('reason', 'no reason')}"


def _trace_grounded_reason(task: CapabilityTask, payload: dict[str, Any], outcome: Outcome) -> tuple[ReasonCode, str]:
    if outcome in {"success", "honest_stop"}:
        return "unknown", ""
    if payload.get("timed_out"):
        return "budget_exhausted", "harness"
    final = str(payload["state"].get("final_response") or "").lower()
    if str(payload["state"].get("graph_status") or "") == "error" or "provider/tool error" in final:
        return "provider_error", "provider"
    for event in payload.get("events") or ():
        name, details = str(event.get("event") or ""), str(event.get("details") or "")
        if name == "tool_unmapped" or (name == "execute" and details == "skipped"):
            return "tool_gap", details or "tool"
        if name == "metacognition_stop" or "agentic budget" in final:
            return "budget_exhausted", "metacognition"
        if name == "verify" and details == "failed":
            return "verification_failed", "verifier"
        if name == "execute" and details == "planner_done" and task.oracle.expected_artifact:
            return "planner_strategy", "planner"
        if name == "fail":
            return "provider_error" if "exception" in details.lower() else "unknown", "harness"
    return ("memory_retrieval", "memory") if task.category == "memory" and outcome != "success" else ("unknown", "")


def make_report(
    *,
    status: Literal["complete", "deferred"],
    manifest: CapabilityManifest,
    started_at: str,
    provider_status: str,
    evaluator_status: str,
    model_config: dict[str, Any],
    command: str,
    results: tuple[CapabilityTaskResult, ...] = (),
    workspace_root: str = "",
    deferred_reason: str = "",
) -> CapabilityReport:
    counts = {key: 0 for key in ("success", "partial", "fail", "honest_stop")}
    reasons = {key: 0 for key in ALLOWED_REASON_CODES}
    for result in results:
        counts[result.outcome] += 1
        reasons[result.reason_code] += 1
    return CapabilityReport(
        status,
        manifest.manifest_id,
        manifest.manifest_sha,
        started_at,
        datetime.now(timezone.utc).isoformat(),
        _git_metadata()[0],
        _git_metadata()[1],
        command,
        provider_status,
        evaluator_status,
        model_config,
        probe_openclaw(),
        workspace_root,
        results,
        counts,
        reasons,
        deferred_reason,
    )


def probe_openclaw() -> dict[str, Any]:
    configured = bool(shutil.which("openclaw") or importlib.util.find_spec("openclaw"))
    return {
        "status": "configured" if configured else "deferred",
        "reason": "" if configured else "OpenClaw/Claw-SWE-Bench not configured locally",
        "openclaw_command": shutil.which("openclaw") or "",
        "openclaw_module": bool(importlib.util.find_spec("openclaw")),
    }


def write_report(report: CapabilityReport, path: str | Path | None = None) -> dict[str, Any]:
    payload = asdict(report)
    if path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _has_existing_artifact(payload: dict[str, Any]) -> bool:
    for artifact in payload.get("artifacts") or ():
        path = str(artifact.get("path") or "")
        if path and Path(path).exists():
            return True
    return any(Path(match).expanduser().exists() for match in PathPattern.findall(str(payload["state"].get("final_response") or "")))


def _looks_like_honest_stop(lowered: str) -> bool:
    markers = ("approval", "i can't", "i cannot", "could not", "cannot", "need", "requires", "missing", "unavailable", "do not have", "don't have", "stopped", "gap")
    return any(marker in lowered for marker in markers)


def _git_metadata() -> tuple[str, str]:
    git = Path(".git")
    head = (git / "HEAD").read_text(encoding="utf-8", errors="ignore").strip() if (git / "HEAD").exists() else ""
    if head.startswith("ref: "):
        ref = head.removeprefix("ref: ").strip()
        commit = (git / ref).read_text(encoding="utf-8", errors="ignore").strip() if (git / ref).exists() else ""
        return commit, ref.rsplit("/", 1)[-1]
    return head, ""


__all__ = [
    "ALLOWED_REASON_CODES",
    "CapabilityManifest",
    "CapabilityOracle",
    "CapabilityReport",
    "CapabilityTask",
    "CapabilityTaskResult",
    "build_maya_domain_capability_manifest",
    "build_openai_planner_llm",
    "build_openai_semantic_evaluator",
    "make_report",
    "probe_openclaw",
    "run_capability_baseline",
    "scripted_planner_llm",
    "write_report",
]
