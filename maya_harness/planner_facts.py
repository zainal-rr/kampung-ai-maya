from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


MAX_PLANNER_FACTS = 6
MAX_CONTENT_SUMMARY_CHARS = 700
MAX_PATTERN_FACTS = 2
MAX_METACOGNITION_FACTS = 2


@dataclass(frozen=True)
class PlannerFact:
    source: str
    title: str = ""
    url: str = ""
    content_summary: str = ""
    text_hash: str = ""
    confidence: float = 0.0
    provenance: tuple[str, ...] = field(default_factory=tuple)
    untrusted_influence: bool = False
    injection_detected: bool = False
    untrusted_source: str = ""
    untrusted_signals: tuple[str, ...] = field(default_factory=tuple)
    instruction_trust: str = "content_only"
    control_eligible: bool = False

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["provenance"] = list(self.provenance)
        data["untrusted_signals"] = list(self.untrusted_signals)
        return data


def planner_fact_from_observation(observation: dict[str, Any]) -> PlannerFact:
    source = str(observation.get("source") or "unknown")
    summary = str(observation.get("text_summary") or observation.get("screen_summary") or "").strip()
    if len(summary) > MAX_CONTENT_SUMMARY_CHARS:
        summary = summary[: MAX_CONTENT_SUMMARY_CHARS - 3].rstrip() + "..."
    untrusted = bool(observation.get("untrusted_influence"))
    injection = bool(observation.get("injection_detected"))
    return PlannerFact(
        source=source,
        title=str(observation.get("page_title") or observation.get("frontmost_app") or ""),
        url=str(observation.get("url") or ""),
        content_summary=summary,
        text_hash=str(observation.get("text_hash") or ""),
        confidence=float(observation.get("confidence") or 0.0),
        provenance=tuple(str(item) for item in (observation.get("provenance") or ())),
        untrusted_influence=untrusted,
        injection_detected=injection,
        untrusted_source=str(observation.get("untrusted_source") or source if untrusted else ""),
        untrusted_signals=tuple(str(item) for item in (observation.get("untrusted_signals") or ())),
        instruction_trust="reference_only" if untrusted else "content_only",
        control_eligible=False,
    )


def append_planner_fact(state: dict[str, Any], observation: dict[str, Any]) -> None:
    fact = planner_fact_from_observation(observation)
    facts = [dict(item) for item in (state.get("planner_facts") or []) if isinstance(item, dict)]
    facts.append(fact.as_dict())
    state["planner_facts"] = compact_planner_facts(facts)


def append_pattern_facts(state: dict[str, Any], pattern_facts: list[dict[str, Any]]) -> None:
    facts = [
        dict(item)
        for item in (state.get("planner_facts") or [])
        if isinstance(item, dict) and item.get("source") != "pattern_recognition"
    ]
    facts.extend(dict(item) for item in pattern_facts if isinstance(item, dict))
    state["planner_facts"] = compact_planner_facts(facts)


def compact_planner_facts(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clean = [dict(item) for item in facts if isinstance(item, dict)]
    live = [item for item in clean if item.get("source") not in {"metacognition", "pattern_recognition"}]
    meta = [item for item in clean if item.get("source") == "metacognition"]
    patterns = [item for item in clean if item.get("source") == "pattern_recognition"]

    meta_recent = meta[-MAX_METACOGNITION_FACTS:]
    live_budget = max(0, MAX_PLANNER_FACTS - len(meta_recent))
    base = [*live[-live_budget:], *meta_recent]
    if len(base) > MAX_PLANNER_FACTS:
        return base[-MAX_PLANNER_FACTS:]

    pattern_budget = min(MAX_PATTERN_FACTS, MAX_PLANNER_FACTS - len(base))
    if pattern_budget <= 0:
        return base
    return [*base, *patterns[-pattern_budget:]]


def planner_fact_block(state: dict[str, Any]) -> str:
    facts = [dict(item) for item in (state.get("planner_facts") or []) if isinstance(item, dict)]
    if not facts and isinstance(state.get("last_observation"), dict) and state.get("last_observation"):
        facts = [planner_fact_from_observation(dict(state["last_observation"])).as_dict()]
    recent = compact_planner_facts(facts)
    if not recent:
        return "(none yet)"
    return json.dumps(recent, ensure_ascii=True, sort_keys=True)
