from __future__ import annotations

import json
from typing import Any, Mapping


TASK_CATEGORIES = {
    "lookup", "field_extraction", "summarization", "comparison",
    "local_artifact", "question_answer", "workflow_repair", "unknown",
}
SOURCE_TYPES = {"email", "web", "file", "meeting", "screen", "memory", "none", "unknown"}
GOAL_TYPES = {"answer", "extract", "compare", "summarize", "create_local_artifact", "ask_owner", "unknown"}
METHOD_STEPS = {
    "read_source", "extract_field", "compare", "summarize",
    "create_local_artifact", "ask_owner", "answer_with_gaps",
}
PROVENANCE_VALUES = {"owner_only", "untrusted_touched"}
SUPERSESSION_VALUES = {"active", "superseded", "forgotten"}
OWNER_PROVENANCE = {"owner", "owner_text", "telegram_owner", "imac", "keyboard", "user"}
MAX_RETRIEVED_PATTERNS = 2


def normalize_situation_shape(raw: Mapping[str, Any] | None) -> dict[str, str]:
    data = dict(raw or {})
    return {
        "task_category": _enum_value(data.get("task_category"), TASK_CATEGORIES),
        "source_type": _enum_value(data.get("source_type"), SOURCE_TYPES),
        "goal_type": _enum_value(data.get("goal_type"), GOAL_TYPES),
    }


def normalize_method(raw: Any) -> tuple[str, ...]:
    if isinstance(raw, str):
        candidates = [raw]
    elif isinstance(raw, (list, tuple)):
        candidates = [str(item) for item in raw]
    else:
        candidates = []
    steps: list[str] = []
    for item in candidates:
        step = item.strip()
        if step in METHOD_STEPS and step not in steps:
            steps.append(step)
    return tuple(steps)


def normalize_outcome(raw: Any) -> str:
    text = str(raw or "").strip()
    if text == "succeeded":
        return text
    if text.startswith("failed:"):
        reason = text.split(":", 1)[1].strip().replace("-", "_")
        if reason and all(ch.isalnum() or ch == "_" for ch in reason):
            return f"failed:{reason[:80]}"
    return "failed:unknown"


def normalize_provenance(raw: Any) -> str:
    text = str(raw or "").strip()
    return text if text in PROVENANCE_VALUES else "untrusted_touched"


def trust_tier_for(provenance: str) -> str:
    return "method_safe" if provenance == "owner_only" else "quarantined"


def derive_situation_shape(state: Mapping[str, Any]) -> dict[str, str]:
    text = f"{state.get('goal') or ''} {state.get('user_text') or ''}".lower()
    workflow = str(state.get("workflow_type") or "").lower()
    observation = dict(state.get("last_observation") or {})
    source = str(observation.get("source") or "").lower()
    return normalize_situation_shape({
        "task_category": _task_category(text, workflow),
        "source_type": _source_type(source, workflow),
        "goal_type": _goal_type(text, workflow),
    })


def derive_method(state: Mapping[str, Any]) -> tuple[str, ...]:
    text = f"{state.get('goal') or ''} {state.get('user_text') or ''}".lower()
    workflow = str(state.get("workflow_type") or "").lower()
    action = dict(state.get("planned_action") or {})
    tool = str(action.get("tool") or state.get("last_successful_step") or "").replace("_", ".", 1)
    steps: list[str] = []
    if workflow in {"browser", "screen"} or tool in {"browser.inspect", "screen.capture"}:
        steps.append("read_source")
    if any(word in text for word in ("extract", "find", "lookup", "search")):
        steps.append("extract_field")
    if any(word in text for word in ("compare", "difference", "versus", " vs ")):
        steps.append("compare")
    if any(word in text for word in ("summarize", "summary", "recap")):
        steps.append("summarize")
    if tool in {"docx.create", "xlsx.create", "pptx.create", "file.create"} or workflow == "document":
        steps.append("create_local_artifact")
    if state.get("pending_approval"):
        steps.append("ask_owner")
    if state.get("final_response"):
        steps.append("answer_with_gaps")
    return normalize_method(steps or ["answer_with_gaps"])


def derive_outcome(state: Mapping[str, Any]) -> str:
    if state.get("last_error"):
        return "failed:tool_error"
    if state.get("pending_approval"):
        return "failed:approval_required"
    if state.get("goal_satisfied") or state.get("final_response"):
        return "succeeded"
    return "failed:unknown"


def derive_episode_provenance(state: Mapping[str, Any]) -> str:
    if state.get("untrusted_influence") or state.get("injection_detected"):
        return "untrusted_touched"
    facts = [dict(item) for item in (state.get("planner_facts") or []) if isinstance(item, dict)]
    if not facts:
        return "untrusted_touched"
    if any(fact.get("untrusted_influence") or fact.get("injection_detected") for fact in facts):
        return "untrusted_touched"
    if any("untrusted_touched" in {str(item) for item in fact.get("provenance") or []} for fact in facts):
        return "untrusted_touched"
    state_provenance = [str(item) for item in (state.get("provenance") or []) if str(item)]
    if not state_provenance or any(item not in OWNER_PROVENANCE for item in state_provenance):
        return "untrusted_touched"
    for fact in facts:
        provenance = [str(item) for item in (fact.get("provenance") or []) if str(item)]
        if not provenance or any(item not in OWNER_PROVENANCE for item in provenance):
            return "untrusted_touched"
    return "owner_only"


def pattern_fact_from_row(row: Mapping[str, Any]) -> dict[str, Any]:
    method = json.loads(str(row.get("method_json") or "[]"))
    provenance = str(row.get("provenance") or "untrusted_touched")
    shape = {key: str(row.get(key) or "unknown") for key in ("task_category", "source_type", "goal_type")}
    summary = (
        "Pattern method hint only; values omitted. "
        f"shape={json.dumps(shape, sort_keys=True)}; method={' -> '.join(method)}; "
        f"outcome={row.get('outcome')}; trust_tier={row.get('trust_tier')}"
    )
    return {
        "source": "pattern_recognition",
        "title": f"pattern:{row.get('pattern_id')}",
        "content_summary": summary[:700],
        "text_hash": str(row.get("pattern_id") or ""),
        "confidence": 0.55 if provenance == "owner_only" else 0.35,
        "provenance": ["pattern_recognition", provenance, str(row.get("trust_tier") or "quarantined")],
        "untrusted_influence": provenance != "owner_only",
        "injection_detected": False,
        "untrusted_source": "pattern_recognition" if provenance != "owner_only" else "",
        "untrusted_signals": ["quarantined_pattern"] if provenance != "owner_only" else [],
        "instruction_trust": "reference_only",
        "control_eligible": False,
    }


def _enum_value(value: Any, allowed: set[str]) -> str:
    text = str(value or "unknown").strip()
    return text if text in allowed else "unknown"


def _task_category(text: str, workflow: str) -> str:
    if workflow == "document" or any(word in text for word in ("create", "write", "draft", "document", "spreadsheet")):
        return "local_artifact"
    if any(word in text for word in ("extract", "field", "pull out")):
        return "field_extraction"
    if any(word in text for word in ("summarize", "summary", "recap")):
        return "summarization"
    if any(word in text for word in ("compare", "difference", "versus", " vs ")):
        return "comparison"
    if any(word in text for word in ("lookup", "search", "find")):
        return "lookup"
    if "repair" in text or "retry" in text:
        return "workflow_repair"
    return "question_answer" if text.strip() else "unknown"


def _source_type(source: str, workflow: str) -> str:
    value = source or workflow
    if value in {"browser", "web", "webpage"}:
        return "web"
    if value in {"office_document", "document", "file"}:
        return "file"
    if value in {"meet", "meeting", "recall"}:
        return "meeting"
    if value in {"screen", "screen_ocr"}:
        return "screen"
    if value in {"memory", "memory_recall"}:
        return "memory"
    if value in {"email", "inbox"}:
        return "email"
    return "none" if not value else "unknown"


def _goal_type(text: str, workflow: str) -> str:
    if workflow == "document" or any(word in text for word in ("create", "write", "draft", "document", "spreadsheet")):
        return "create_local_artifact"
    if any(word in text for word in ("extract", "find", "lookup", "search")):
        return "extract"
    if any(word in text for word in ("compare", "difference", "versus", " vs ")):
        return "compare"
    if any(word in text for word in ("summarize", "summary", "recap")):
        return "summarize"
    if any(word in text for word in ("approval", "permission", "confirm")):
        return "ask_owner"
    return "answer" if text.strip() else "unknown"
