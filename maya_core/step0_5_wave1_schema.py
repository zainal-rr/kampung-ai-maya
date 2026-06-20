from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal, Mapping


LlmCall = Callable[[str], Awaitable[str]]
ReaderMode = Literal["projection", "provider"]


@dataclass(frozen=True)
class ReaderInput:
    source: str
    lane_id: str
    title: str
    raw_text: str
    source_kind: str
    untrusted: bool = True
    injection_detected: bool = False
    signals: tuple[str, ...] = ()


@dataclass(frozen=True)
class EffectBinding:
    effect_id: str
    tool_name: str
    action_type: str
    args: Mapping[str, Any] = field(default_factory=dict)
    field_provenance: Mapping[str, Any] = field(default_factory=dict)
    browser_context: Mapping[str, Any] = field(default_factory=dict)
    source_kind: str = "unknown"
    untrusted_influence: bool = True
    injection_detected: bool = False
    discloses_private: bool = False
    always_evaluate: bool = False
    required_for_utility: bool = False


@dataclass(frozen=True)
class CaseBinding:
    case_id: str
    observations: tuple[ReaderInput, ...]
    effects: tuple[EffectBinding, ...] = ()
    fallback_answer: str = ""
    workflow_type: str = "step0_5"


SCOPE = {
    "exercises": [
        "reader executor binding",
        "real or deterministic reader-to-PlannerFact projection",
        "real GPT planner when OPENAI_API_KEY is configured",
        "MayaPermissionKernel",
        "safe fake effect sink",
        "Meet disclosure policy for disclosure probes",
    ],
    "does_not_exercise": [
        "real external send/payment/delete emission",
        "live Google Meet audio",
        "real Telegram/file delivery",
    ],
    "safe_effect_sink": True,
}
