"""Model-in-the-loop planning hooks for the harness graph.

This module turns the MayaToolRegistry into provider-style function-calling
schemas and gives the harness graph three model hooks:

1. ``plan_with_llm``     - model-generated plan steps (falls back to ``plan_for``)
2. ``choose_next_action``- pick the next tool call or declare the goal done
3. ``verify_goal``       - ask whether the last observation satisfies the goal

All hooks accept an ``llm_call`` async callable (prompt str -> response str) so
the harness stays provider-agnostic and deterministic smokes can inject fakes.
When no ``llm_call`` is wired in, the harness keeps its template behavior.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any

from harness_workflows import plan_for
from maya_tool_registry import default_maya_tool_registry

LlmCall = Callable[[str], Awaitable[str]]

logger = logging.getLogger(__name__)

MAX_OBSERVATIONS_IN_PROMPT = 6


def tool_schemas_for_llm() -> list[dict[str, Any]]:
    """Convert MayaToolSpec registry entries into function-calling schemas."""
    registry = default_maya_tool_registry()
    return [
        {
            "name": spec.name.replace(".", "_"),
            "description": spec.description,
            "input_schema": spec.input_schema or {"type": "object", "properties": {}},
        }
        for spec in registry.list()
    ]


async def plan_with_llm(state: dict[str, Any], llm_call: LlmCall) -> list[str]:
    """Ask the model for a short plan. Falls back to the static template."""
    fallback = plan_for(str(state.get("workflow_type") or "general"))
    prompt = (
        "You are planning the next steps for a local personal-agent workflow.\n"
        f"Goal: {state.get('goal') or state.get('user_text', '')}\n"
        f"Workflow type: {state.get('workflow_type', 'general')}\n"
        f"Observations so far: {_observation_block(state)}\n"
        "Reply with a JSON array of 2-5 short imperative step strings. JSON only."
    )
    try:
        raw = await llm_call(prompt)
        steps = _parse_json(raw)
        if isinstance(steps, list) and steps and all(isinstance(s, str) for s in steps):
            return [s.strip() for s in steps[:5] if s.strip()] or fallback
    except Exception:
        logger.exception("LLM plan generation failed; using template plan")
    return fallback


async def choose_next_action(state: dict[str, Any], llm_call: LlmCall, knowledge: str = "") -> dict[str, Any]:
    """One model call: pick the next tool call or declare the goal complete.

    Returns ``{"tool": str, "args": dict}`` or ``{"done": True, "answer": str}``.
    On any failure, returns done=True so the loop degrades to single-pass.
    ``knowledge`` carries per-step domain retrieval (recipes, concept docs).
    """
    tools = tool_schemas_for_llm()
    knowledge_block = f"\nRelevant domain knowledge:\n{knowledge[:4000]}\n" if knowledge else ""
    prompt = (
        "You are executing a local personal-agent workflow one step at a time.\n"
        f"Goal: {state.get('goal') or state.get('user_text', '')}\n"
        f"Plan: {', '.join(state.get('plan') or [])}\n"
        f"Steps used: {int(state.get('current_step') or 0)}\n"
        f"Observations so far: {_observation_block(state)}\n"
        f"{knowledge_block}"
        f"Available tools: {json.dumps(tools)}\n"
        'Reply with JSON only. Either {"tool": "<name>", "args": {...}} for the '
        'single next tool call, or {"done": true, "answer": "<final answer>"} '
        "if the goal is satisfied or no tool helps. Tool names use dots "
        '(for example "memory.write"), exactly as listed.'
    )
    try:
        decision = _parse_json(await llm_call(prompt))
        if isinstance(decision, dict) and (decision.get("done") or decision.get("tool")):
            return decision
    except Exception:
        logger.exception("LLM next-action selection failed; finishing loop")
    return {"done": True, "answer": str(state.get("final_response") or "")}


async def verify_goal(state: dict[str, Any], llm_call: LlmCall) -> bool:
    """Ask the model whether the goal is satisfied. FAIL-CLOSED.

    A verifier that cannot confirm success must not claim it (council review
    W1, 2026-06-11: the old default-True turned a broken verifier into a
    silent "done" — a safety defect once untrusted users can invoke the loop).
    Only an explicit YES satisfies the goal. On error or ambiguity, one
    reflective retry; then return False. False keeps the loop open — which is
    safe precisely because MAX_STEPS bounds it: fail-closed verifier + hard
    budget = never-falsely-done AND never-infinite."""
    base_prompt = (
        "A local personal-agent workflow just executed a step.\n"
        f"Goal: {state.get('goal') or state.get('user_text', '')}\n"
        f"Latest result: {str(state.get('final_response', ''))[:600]}\n"
        f"Observations so far: {_observation_block(state)}\n"
        "Is the goal fully satisfied? Reply with exactly YES or NO."
    )
    prompt = base_prompt
    for attempt in range(2):  # initial + one reflective retry
        try:
            raw = (await llm_call(prompt)).strip().upper()
            if raw.startswith("YES"):
                return True
            if raw.startswith("NO"):
                return False
            # Ambiguous: reflect once with a tighter instruction, then fail closed.
            prompt = base_prompt + "\nAnswer with exactly YES or NO and nothing else."
        except Exception:
            logger.exception("LLM goal verification failed (attempt %d); fail-closed", attempt + 1)
    return False


def _observation_block(state: dict[str, Any]) -> str:
    observations = [str(item) for item in (state.get("observations") or [])]
    recent = observations[-MAX_OBSERVATIONS_IN_PROMPT:]
    return " | ".join(recent) if recent else "(none yet)"


def _parse_json(raw: str) -> Any:
    """Parse model output as JSON, tolerating markdown code fences."""
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for index, char in enumerate(text):
            if char not in "[{":
                continue
            try:
                value, _end = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            return value
        raise
