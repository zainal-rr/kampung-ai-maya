from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal

Outcome = Literal["success", "partial", "fail", "honest_stop"]
OracleType = Literal["artifact", "semantic_answer", "honest_stop", "approval_required"]
ReasonCode = Literal[
    "context_missing",
    "tool_gap",
    "planner_strategy",
    "verification_failed",
    "memory_retrieval",
    "budget_exhausted",
    "provider_error",
    "unknown",
]
LlmCall = Callable[[str], Awaitable[str]]
SemanticEvaluator = Callable[[str, "CapabilityTask", dict[str, Any]], Awaitable[dict[str, str]]]

ALLOWED_REASON_CODES: tuple[ReasonCode, ...] = (
    "context_missing",
    "tool_gap",
    "planner_strategy",
    "verification_failed",
    "memory_retrieval",
    "budget_exhausted",
    "provider_error",
    "unknown",
)


@dataclass(frozen=True)
class CapabilityOracle:
    oracle_type: OracleType
    rubric: str = ""
    allows_honest_stop: bool = False
    expected_artifact: bool = False


@dataclass(frozen=True)
class CapabilityTask:
    task_id: str
    category: str
    prompt: str
    oracle: CapabilityOracle
    workflow_type: str = ""
    max_steps: int = 5
    timeout_s: float = 45.0


@dataclass(frozen=True)
class CapabilityManifest:
    manifest_id: str
    tasks: tuple[CapabilityTask, ...]
    manifest_sha: str = ""


@dataclass(frozen=True)
class CapabilityTaskResult:
    task_id: str
    category: str
    outcome: Outcome
    reason_code: ReasonCode
    first_broken_component: str
    oracle_type: OracleType
    oracle_status: str
    final_answer: str
    graph_status: str
    events: tuple[dict[str, str], ...] = ()
    artifacts: tuple[dict[str, str], ...] = ()
    elapsed_s: float = 0.0
    timed_out: bool = False


@dataclass(frozen=True)
class CapabilityReport:
    status: Literal["complete", "deferred"]
    manifest_id: str
    manifest_sha: str
    started_at: str
    finished_at: str
    product_commit: str
    branch: str
    command: str
    provider_status: str
    evaluator_status: str
    model_config: dict[str, Any]
    openclaw_probe: dict[str, Any]
    workspace_root: str = ""
    results: tuple[CapabilityTaskResult, ...] = ()
    counts: dict[str, int] = field(default_factory=dict)
    reason_counts: dict[str, int] = field(default_factory=dict)
    deferred_reason: str = ""
