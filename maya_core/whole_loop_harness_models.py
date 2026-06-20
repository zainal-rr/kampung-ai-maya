from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping


Quadrant = Literal["secure/useful", "secure/not-useful", "unsafe/useful", "unsafe/not-useful"]


@dataclass(frozen=True)
class LaneEvent:
    case_id: str
    lane_id: str
    event_type: str
    raw_untrusted_seen: bool = False
    effect_id: str = ""
    effect_target: str = ""
    gate_decision: str = "none"
    outcome: str = "observed"
    discloses_private: bool = False
    detail: str = ""
    input_hash: str = ""
    output_hash: str = ""
    parent_span_id: str = ""
    span_id: str = ""
    sequence: int = 0
    control_eligible: bool = False
    source_kind: str = ""
    source_id: str = ""


@dataclass(frozen=True)
class WholeLoopTrace:
    case_id: str
    run_index: int
    run_id: str
    events: tuple[LaneEvent, ...] = ()


@dataclass(frozen=True)
class EnvironmentSnapshot:
    case_id: str
    phase: Literal["pre", "post"]
    isolated_db: str = ""
    state_hash: str = ""
    facts: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ScenarioOracle:
    forbidden_effect_ids: tuple[str, ...] = ()
    required_blocked_effect_ids: tuple[str, ...] = ()
    required_executed_effect_ids: tuple[str, ...] = ()
    required_answer_fragments: tuple[str, ...] = ()
    required_lane_ids: tuple[str, ...] = ()
    utility_failure_lane: str = "task"


@dataclass(frozen=True)
class WholeLoopScenario:
    case_id: str
    input_text: str
    oracle: ScenarioOracle
    timeout_s: float = 5.0
    category: str = "open_dummy"


@dataclass(frozen=True)
class ScenarioManifest:
    manifest_id: str
    scenarios: tuple[WholeLoopScenario, ...]
    sealed: bool = False
    manifest_sha: str = ""


@dataclass(frozen=True)
class ModelConfig:
    provider: str = "dummy"
    model: str = "dummy"
    temperature: float = 0.0
    seed: str = ""


@dataclass(frozen=True)
class WholeLoopOutput:
    case_id: str
    final_answer: str
    trace: tuple[LaneEvent, ...] = ()
    timed_out: bool = False


@dataclass(frozen=True)
class RunRecord:
    case_id: str
    run_index: int
    run_id: str
    output: WholeLoopOutput
    trace: WholeLoopTrace
    pre_snapshot: EnvironmentSnapshot
    post_snapshot: EnvironmentSnapshot
    elapsed_s: float = 0.0


@dataclass(frozen=True)
class CaseScore:
    case_id: str
    secure: bool
    useful: bool
    quadrant: Quadrant
    first_broken_lane: str
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class WholeLoopReport:
    scores: tuple[CaseScore, ...]
    counts: dict[str, int]
    complete: bool
    manifest_id: str = ""
    runs_per_case: int = 1
    model_config: ModelConfig = field(default_factory=ModelConfig)
    run_records: tuple[RunRecord, ...] = ()
    case_aggregates: dict[str, dict[str, Any]] = field(default_factory=dict)
