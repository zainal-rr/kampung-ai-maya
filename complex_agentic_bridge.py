from __future__ import annotations

import re
from dataclasses import dataclass

from harness_state import initial_harness_state
from harness_store import create_approval, new_run_id, record_event, upsert_run
from harness_workflows import classify_workflow


@dataclass(frozen=True)
class ComplexAgenticWorkflow:
    run_id: str
    workflow_type: str
    steps: list[str]
    approval_action: str


def should_create_agentic_workflow(text: str) -> bool:
    lowered = " ".join(text.lower().split())
    if any(marker in lowered for marker in ("plan only", "just plan", "do not execute", "don't execute", "no execution")):
        return False
    return any(
        marker in lowered
        for marker in (
            "self heal",
            "self-heal",
            "self healing",
            "repair maya",
            "fix maya",
            "agentic workflow",
            "turn this into a workflow",
            "make this a workflow",
            "execute after approval",
            "implement after approval",
        )
    )


def should_route_complex_plan(text: str) -> bool:
    lowered = " ".join(text.lower().split())
    return should_create_agentic_workflow(lowered)


async def create_agentic_workflow_from_complex_plan(
    db_path: str | None,
    *,
    source_run_id: str,
    request: str,
    plan: str,
    review: str,
    graph: list[dict[str, str]],
    channel: str,
) -> ComplexAgenticWorkflow | None:
    if not db_path:
        return None
    workflow_type = _workflow_type(request)
    run_id = new_run_id()
    steps = _executable_steps(request, plan, graph, workflow_type)
    approval_action = _approval_action(request, workflow_type)
    state = initial_harness_state(
        run_id=run_id,
        thread_id=f"harness:{run_id}",
        channel=channel,
        user_text=approval_action,
        workflow_type=workflow_type,
        goal=f"Execute approved /complex plan: {_compact(request, 160)}",
    )
    state.update(
        {
            "graph_status": "waiting_approval",
            "plan": steps,
            "pending_approval": {
                "action": approval_action,
                "details": _approval_details(source_run_id, workflow_type, steps, review),
            },
            "source_complex_run_id": source_run_id,
            "complex_request": request,
            "complex_plan": plan,
            "complex_review": review,
            "executable_steps": steps,
            "approval_required": True,
        }
    )
    await upsert_run(db_path, state, status="paused")
    await create_approval(db_path, run_id, "execute_complex_plan", state["pending_approval"]["details"])
    await record_event(db_path, run_id, "complex_plan_linked", f"source={source_run_id}; workflow_type={workflow_type}")
    await record_event(db_path, run_id, "approval_gate", "waiting for approval to execute /complex plan")
    return ComplexAgenticWorkflow(run_id=run_id, workflow_type=workflow_type, steps=steps, approval_action=approval_action)


def format_agentic_workflow_notice(workflow: ComplexAgenticWorkflow | None) -> str:
    if workflow is None:
        return ""
    lines = [
        "Agentic workflow prepared:",
        f"1) execution workflow: {workflow.run_id}",
        f"2) type: {workflow.workflow_type}",
        "3) status: waiting for approval",
        "4) next: say yes/go to start it, or cancel to stop it",
    ]
    return "\n".join(lines)


def _workflow_type(request: str) -> str:
    lowered = " ".join(request.lower().split())
    if any(marker in lowered for marker in ("self heal", "self-heal", "self healing", "repair maya", "fix maya")):
        return "self_heal"
    return classify_workflow(request)


def _executable_steps(request: str, plan: str, graph: list[dict[str, str]], workflow_type: str) -> list[str]:
    if workflow_type == "self_heal":
        return [
            "inspect recent logs and code-health signals",
            "localize the likely failing subsystem",
            "create a repair proposal without changing the main repo",
            "prepare exact targeted tests",
            "wait for approval before patch, restart, deploy, or main-repo apply",
        ]
    steps = [_compact(item.get("task", ""), 120) for item in graph if item.get("task")]
    steps.extend(_steps_from_plan(plan))
    cleaned: list[str] = []
    for step in steps:
        normalized = _compact(step, 140)
        if normalized and normalized.lower() not in {item.lower() for item in cleaned}:
            cleaned.append(normalized)
        if len(cleaned) >= 6:
            break
    if not cleaned:
        cleaned = [
            "execute the approved plan safely",
            "record artifacts and decisions",
            "verify the result before reporting completion",
        ]
    if not any("verify" in step.lower() or "test" in step.lower() for step in cleaned):
        cleaned.append("verify the result before reporting completion")
    return cleaned[:7]


def _steps_from_plan(plan: str) -> list[str]:
    steps: list[str] = []
    for line in plan.splitlines():
        stripped = line.strip(" -\t")
        if not stripped:
            continue
        if re.match(r"^(?:\d+[\).]|[a-z][\).])\s+", stripped, re.I):
            stripped = re.sub(r"^(?:\d+[\).]|[a-z][\).])\s+", "", stripped)
            steps.append(stripped)
    return steps


def _approval_action(request: str, workflow_type: str) -> str:
    if workflow_type == "self_heal":
        return f"self heal from approved complex plan: {request}"
    return f"execute approved complex plan: {request}"


def _approval_details(source_run_id: str, workflow_type: str, steps: list[str], review: str) -> str:
    step_text = "; ".join(steps[:5])
    review_summary = _compact(review, 300) if review else "No Steward review text recorded."
    return (
        f"Source /complex workflow: {source_run_id}\n"
        f"Workflow type: {workflow_type}\n"
        f"Executable steps: {step_text}\n"
        f"Steward review summary: {review_summary}\n"
        "Approval starts the harness workflow. Repo patching, restart, deploy, delete, upload, booking, payment, and main-repo apply still require explicit approval."
    )


def _compact(text: str, limit: int) -> str:
    return " ".join(text.strip().split())[:limit]
