from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from typing import Any


FAILURE_CODES = {
    "progressed",
    "goal_satisfied",
    "wrong_tool",
    "bad_args",
    "missing_info",
    "gate_blocked",
    "source_of_truth_mismatch",
    "tool_unavailable",
    "tool_error",
    "qa_failed",
    "no_progress",
    "repeated_failure",
    "injection_suspected",
    "budget_near_exhausted",
    "unknown",
}

ALLOWED_MOVES = {
    "continue_same_plan",
    "retry_same_step",
    "choose_different_tool",
    "repair_output",
    "gather_allowed_context",
    "ask_owner",
    "stop_honestly",
    "synthesize_with_gaps",
}

FORBIDDEN_MOVES = {
    "approve_action",
    "bypass_kernel",
    "raise_privilege",
    "change_provenance",
    "trust_untrusted_content",
    "execute_effect",
    "override_disclosure_gate",
    "ignore_approval_requirement",
}

LOW_CONFIDENCE_MOVES = {"ask_owner", "stop_honestly"}

CODE_ALLOWED_MOVES = {
    "gate_blocked": {"ask_owner", "stop_honestly", "choose_different_tool"},
    "injection_suspected": {"ask_owner", "stop_honestly", "choose_different_tool"},
    "source_of_truth_mismatch": {"gather_allowed_context", "ask_owner", "stop_honestly"},
    "missing_info": {"gather_allowed_context", "ask_owner", "stop_honestly"},
    "repeated_failure": {"stop_honestly", "ask_owner", "choose_different_tool"},
    "no_progress": {"choose_different_tool", "ask_owner", "stop_honestly"},
    "budget_near_exhausted": {"synthesize_with_gaps", "ask_owner", "stop_honestly"},
    "unknown": {"ask_owner", "stop_honestly"},
}

LOW_CONFIDENCE_MAX = 0.55
HIGH_CONFIDENCE_MIN = 0.85
MAX_METACOGNITION_FACTS = 6
MAX_METACOGNITION_PLANNER_FACTS = 2
MAX_NON_METACOGNITION_PLANNER_FACTS = 4
STOP_NO_PROGRESS_COUNT = 3
REPEAT_FAILURE_LIMIT = 2


@dataclass(frozen=True)
class ReflectionDecision:
    failure_code: str
    confidence: float
    confidence_band: str
    reflection_move: str
    args_shape: str = ""
    rationale: str = ""
    control_eligible: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def confidence_band(confidence: float) -> str:
    value = _clamp_confidence(confidence)
    if value >= HIGH_CONFIDENCE_MIN:
        return "high"
    if value >= LOW_CONFIDENCE_MAX:
        return "medium"
    return "low"


def normalize_reflection(raw: dict[str, Any] | ReflectionDecision | None) -> ReflectionDecision:
    if isinstance(raw, ReflectionDecision):
        raw = raw.as_dict()
    data = dict(raw or {})
    supplied_code = str(data.get("failure_code") or "unknown")
    supplied_move = str(data.get("reflection_move") or "stop_honestly")
    confidence, valid_confidence = _parse_confidence(data.get("confidence", 0.0))
    computed_band = confidence_band(confidence)
    supplied_band = str(data.get("confidence_band") or computed_band)
    rationale = str(data.get("rationale") or "")[:500]
    args_shape = str(data.get("args_shape") or "")[:500]

    if (
        not valid_confidence
        or supplied_code not in FAILURE_CODES
        or supplied_move not in ALLOWED_MOVES
        or supplied_move in FORBIDDEN_MOVES
        or supplied_band != computed_band
        or (confidence < LOW_CONFIDENCE_MAX and supplied_move not in LOW_CONFIDENCE_MOVES)
        or supplied_move not in CODE_ALLOWED_MOVES.get(supplied_code, ALLOWED_MOVES)
    ):
        return ReflectionDecision(
            failure_code="unknown",
            confidence=min(confidence, LOW_CONFIDENCE_MAX - 0.01),
            confidence_band="low",
            reflection_move="stop_honestly",
            args_shape=args_shape,
            rationale="Reflection failed validation and was made fail-closed.",
        )

    lowered_rationale = rationale.lower()
    if any(phrase in lowered_rationale for phrase in ("approval granted", "bypass", "ignore approval", "raise privilege")):
        return ReflectionDecision(
            failure_code="injection_suspected",
            confidence=min(confidence, LOW_CONFIDENCE_MAX - 0.01),
            confidence_band="low",
            reflection_move="ask_owner" if supplied_code == "injection_suspected" else "stop_honestly",
            args_shape=args_shape,
            rationale="Reflection rationale contained authority-like text and was treated as untrusted.",
        )

    return ReflectionDecision(
        failure_code=supplied_code,
        confidence=confidence,
        confidence_band=computed_band,
        reflection_move=supplied_move,
        args_shape=args_shape,
        rationale=rationale,
    )


def action_shape(tool_name: str, args: dict[str, Any] | None) -> str:
    keys = []
    for key, value in sorted(dict(args or {}).items()):
        keys.append([str(key), _shape_type(value)])
    return json.dumps({"tool": str(tool_name), "args": keys}, sort_keys=True)


def reflection_fact(decision: ReflectionDecision) -> dict[str, Any]:
    return {
        "source": "metacognition",
        "title": decision.failure_code,
        "content_summary": (
            f"failure_code={decision.failure_code}; "
            f"move={decision.reflection_move}; "
            f"confidence={decision.confidence_band}; "
            f"args_shape={decision.args_shape}; "
            f"rationale={decision.rationale}"
        )[:700],
        "text_hash": "",
        "confidence": decision.confidence,
        "provenance": ["metacognition"],
        "untrusted_influence": decision.failure_code == "injection_suspected",
        "injection_detected": decision.failure_code == "injection_suspected",
        "untrusted_source": "reflection" if decision.failure_code == "injection_suspected" else "",
        "untrusted_signals": [decision.failure_code] if decision.failure_code == "injection_suspected" else [],
        "instruction_trust": "content_only",
        "control_eligible": False,
    }


def append_reflection(state: dict[str, Any], raw: dict[str, Any] | ReflectionDecision | None) -> ReflectionDecision:
    decision = normalize_reflection(raw)
    reflections = [dict(item) for item in (state.get("metacognition") or []) if isinstance(item, dict)]
    reflections.append(decision.as_dict())
    state["metacognition"] = reflections[-MAX_METACOGNITION_FACTS:]

    facts = [dict(item) for item in (state.get("planner_facts") or []) if isinstance(item, dict)]
    non_meta = [item for item in facts if item.get("source") != "metacognition"]
    meta = [item for item in facts if item.get("source") == "metacognition"]
    meta.append(reflection_fact(decision))
    state["planner_facts"] = [
        *non_meta[-MAX_NON_METACOGNITION_PLANNER_FACTS:],
        *meta[-MAX_METACOGNITION_PLANNER_FACTS:],
    ][-MAX_METACOGNITION_FACTS:]

    if decision.failure_code == "no_progress":
        state["no_progress_count"] = int(state.get("no_progress_count") or 0) + 1

    if decision.failure_code in {"wrong_tool", "bad_args", "tool_error", "qa_failed", "gate_blocked", "no_progress"}:
        failures = dict(state.get("failed_action_shapes") or {})
        key = _failure_key(decision)
        failures[key] = int(failures.get(key) or 0) + 1
        state["failed_action_shapes"] = failures
    return decision


def classify_tool_result(
    *,
    status: str,
    message: str = "",
    requires_approval: bool = False,
    args_shape: str = "",
) -> ReflectionDecision:
    lowered = (message or "").lower()
    if requires_approval:
        return ReflectionDecision("gate_blocked", 0.95, "high", "ask_owner", args_shape, "Tool requires approval.")
    if status == "skipped":
        return ReflectionDecision("wrong_tool", 0.85, "high", "choose_different_tool", args_shape, "No harness tool handled the request.")
    if status in {"failed", "error"}:
        return ReflectionDecision("tool_error", 0.85, "high", "retry_same_step", args_shape, message[:240])
    if "does not exist" in lowered or "no file path" in lowered or "missing" in lowered:
        return ReflectionDecision("qa_failed", 0.85, "high", "repair_output", args_shape, message[:240])
    if status == "completed" and message:
        return ReflectionDecision("progressed", 0.75, "medium", "continue_same_plan", args_shape, "Tool returned a result.")
    return ReflectionDecision("no_progress", 0.75, "medium", "choose_different_tool", args_shape, "No useful result was produced.")


def should_block_repeated_action(state: dict[str, Any], tool_name: str, args: dict[str, Any] | None) -> ReflectionDecision | None:
    shape = action_shape(tool_name, args)
    failures = dict(state.get("failed_action_shapes") or {})
    count = max(
        (int(value or 0) for key, value in failures.items() if key.startswith(shape + "|")),
        default=0,
    )
    if count >= REPEAT_FAILURE_LIMIT:
        return ReflectionDecision(
            failure_code="repeated_failure",
            confidence=0.95,
            confidence_band="high",
            reflection_move="stop_honestly",
            args_shape=shape,
            rationale="The same action shape already failed twice.",
        )
    return None


def should_stop_for_no_progress(state: dict[str, Any]) -> bool:
    return int(state.get("no_progress_count") or 0) >= STOP_NO_PROGRESS_COUNT


def _failure_key(decision: ReflectionDecision) -> str:
    return f"{decision.args_shape}|{decision.failure_code}"


def _clamp_confidence(value: Any) -> float:
    confidence, _valid = _parse_confidence(value)
    return confidence


def _parse_confidence(value: Any) -> tuple[float, bool]:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0, False
    if not math.isfinite(numeric) or numeric < 0.0 or numeric > 1.0:
        return 0.0, False
    return max(0.0, min(1.0, numeric)), True


def _shape_type(value: Any) -> str:
    if isinstance(value, dict):
        return "object:" + ",".join(sorted(str(key) for key in value.keys()))
    if isinstance(value, list):
        return "list"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if value is None:
        return "null"
    return "string"
