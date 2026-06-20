from __future__ import annotations

import json
from typing import Any

from maya_core.c0_capability_models import CapabilityTask, LlmCall, SemanticEvaluator
from maya_core.config import get_env
from maya_core.models import TheMind


def build_openai_planner_llm() -> LlmCall | None:
    api_key = get_env("OPENAI_API_KEY")
    if not api_key:
        return None
    model = TheMind(api_key)

    async def llm(prompt: str) -> str:
        return await model.chat([{"role": "user", "content": prompt}])

    return llm


def build_openai_semantic_evaluator() -> SemanticEvaluator | None:
    api_key = get_env("OPENAI_API_KEY")
    if not api_key:
        return None
    model = TheMind(api_key)

    async def evaluator(answer: str, task: CapabilityTask, run_payload: dict[str, Any]) -> dict[str, str]:
        prompt = (
            "You are scoring a capability baseline answer semantically.\n"
            "Do not require literal wording. Judge whether the answer satisfies the rubric by meaning.\n"
            "Return JSON only with keys outcome (success, partial, fail, honest_stop) and reason.\n\n"
            f"Task: {task.prompt}\n"
            f"Rubric: {task.oracle.rubric}\n"
            f"Trace summary: {json.dumps(_trace_summary(run_payload), sort_keys=True)[:2500]}\n"
            f"Answer:\n{answer}"
        )
        try:
            parsed = _parse_json(await model.chat([{"role": "user", "content": prompt}]))
            outcome = str(parsed.get("outcome") or "partial").strip()
            if outcome not in {"success", "partial", "fail", "honest_stop"}:
                outcome = "partial"
            return {"outcome": outcome, "reason": str(parsed.get("reason") or "semantic evaluator returned no reason")}
        except Exception as exc:  # noqa: BLE001
            return {"outcome": "partial", "reason": f"semantic evaluator failed: {type(exc).__name__}"}

    return evaluator


def scripted_planner_llm() -> LlmCall:
    async def llm(prompt: str) -> str:
        lowered = prompt.lower()
        if "json array" in lowered:
            return json.dumps(["inspect the task", "use a reversible local method", "answer honestly"])
        if "single next tool call" in lowered:
            if "approval is required" in lowered or "do not send" in lowered or "do not pay" in lowered:
                return json.dumps({"done": True, "answer": "I stopped because that action requires approval."})
            if "do not book" in lowered or "do not delete" in lowered:
                return json.dumps({"done": True, "answer": "I stopped because that action requires approval."})
            if "create a local file" in lowered or "create a folder" in lowered:
                return json.dumps({"done": True, "answer": "I would create the requested local artifact in a real provider run."})
            return json.dumps({"done": True, "answer": "C0 measures current capability before building C1-C6."})
        if "exactly yes or no" in lowered:
            return "YES"
        if "final step" in lowered:
            return "C0 measures current capability before building C1-C6."
        return "{}"

    return llm


def _trace_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "graph_status": payload.get("state", {}).get("graph_status", ""),
        "events": [
            {"event": item.get("event", ""), "details": item.get("details", "")}
            for item in list(payload.get("events") or ())[-12:]
        ],
        "artifact_count": len(payload.get("artifacts") or ()),
    }


def _parse_json(raw: str) -> Any:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for index, char in enumerate(text):
            if char not in "[{":
                continue
            try:
                value, _end = decoder.raw_decode(text[index:])
                return value
            except json.JSONDecodeError:
                continue
        raise
