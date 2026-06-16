from __future__ import annotations

from typing import TypedDict


class HarnessState(TypedDict, total=False):
    run_id: str
    schema_version: int
    thread_id: str
    channel: str
    user_text: str
    goal: str
    workflow_type: str
    graph_status: str
    active_project_path: str
    plan: list[str]
    current_step: int
    last_successful_step: str
    next_suggested_step: str
    last_user_instruction: str
    user_turn_id: str
    last_observation: dict
    browser_state: dict
    keep_open: bool
    observations: list[str]
    artifacts: list[str]
    pending_approval: dict[str, str]
    approval_result: str
    last_error: str
    final_response: str
    memory_notes: list[str]
    model_lane: str
    cost_recorded: bool
    source_complex_run_id: str
    complex_request: str
    complex_plan: str
    complex_review: str
    executable_steps: list[str]
    approval_required: bool
    self_heal_checkpoint: dict
    agentic_loop: bool
    goal_satisfied: bool
    max_steps: int
    planned_action: dict
    forced_synthesis: bool


def initial_harness_state(
    *,
    run_id: str,
    thread_id: str,
    channel: str,
    user_text: str,
    workflow_type: str = "",
    goal: str = "",
    approval_result: str = "",
) -> HarnessState:
    return {
        "run_id": run_id,
        "schema_version": 1,
        "thread_id": thread_id,
        "channel": channel,
        "user_text": user_text,
        "goal": goal or user_text,
        "workflow_type": workflow_type,
        "graph_status": "planning",
        "plan": [],
        "current_step": 0,
        "last_successful_step": "",
        "next_suggested_step": "",
        "last_user_instruction": user_text,
        "user_turn_id": f"{run_id}:0",
        "last_observation": {},
        "browser_state": {},
        "keep_open": False,
        "observations": [],
        "artifacts": [],
        "pending_approval": {},
        "approval_result": approval_result,
        "last_error": "",
        "final_response": "",
        "memory_notes": [],
        "model_lane": "",
        "cost_recorded": False,
    }
