from __future__ import annotations

import os

from maya_core.complex_agentic_bridge import (
    create_agentic_workflow_from_complex_plan,
    format_agentic_workflow_notice,
)
from maya_core.complex_workflow import run_complex_plan_workflow
from maya_core.cost_tracker import record_usage
from maya_core.lane_prompts import MIND_ESCALATION_PROMPT


async def complex_plan_response(lanes, text: str, memory_context: str, skill_context: str, channel: str = "telegram") -> str:
    if not os.getenv("OPENAI_API_KEY"):
        return "The complex planning lane is not available yet. Add the strategic API key first."
    result = await run_complex_plan_workflow(
        lanes.db_path,
        text,
        research_agent=lambda: _research_context(lanes, text, memory_context, skill_context),
        graph_planner_agent=lambda research: _graph_agent(lanes, text, memory_context, skill_context, research),
        subagent_runner=lambda task, research: _subagent_response(lanes, text, memory_context, skill_context, task, research),
        planner_agent=lambda research, merged: _plan_agent(lanes, text, memory_context, skill_context, research, merged),
        reviewer_agent=lambda plan, research, merged: _review_plan(
            lanes,
            text,
            plan,
            "\n\n".join(block for block in (memory_context, research, merged) if block),
            skill_context,
        ),
    )
    await record_usage(lanes.db_path, "gpt_complex_calls", 1, "complex plan")
    agentic = await create_agentic_workflow_from_complex_plan(
        lanes.db_path,
        source_run_id=result.run_id,
        request=text,
        plan=result.plan,
        review=result.review,
        graph=result.graph,
        channel=channel,
    ) if _wants_agentic_workflow(text) else None
    return _merge_plan_review(result.plan, result.review, result.run_id, format_agentic_workflow_notice(agentic))


async def _research_context(lanes, text: str, memory_context: str, skill_context: str) -> str:
    if not os.getenv("GOOGLE_API_KEY"):
        return ""
    prompt = lanes._prompt(
        "You are Maya's premium research lane. Prepare concise research context for GPT planning. "
        "Separate facts, assumptions, risks, and unknowns. Do not make the plan and do not execute.",
        text,
        memory_context,
        skill_context,
    )
    reply = await lanes.premium_sight.chat(prompt)
    await record_usage(lanes.db_path, "gemini_premium_text_calls", 1, "complex research context")
    return f"Premium research context:\n{reply.strip()}" if reply.strip() else ""


async def _graph_agent(lanes, text: str, memory_context: str, skill_context: str, research: str) -> str:
    if not os.getenv("GOOGLE_API_KEY"):
        return ""
    prompt = lanes._prompt(
        "You are Maya's dynamic workflow planner. Return compact JSON only. "
        "Create 2 to 4 independent subagent tasks that can run in parallel. "
        'Use this exact shape: [{"agent":"risk_agent","task":"..."},{"agent":"implementation_agent","task":"..."}]. '
        "Do not make the final plan.",
        text,
        "\n\n".join(block for block in (memory_context, research) if block),
        skill_context,
    )
    reply = await lanes.premium_sight.chat(prompt)
    await record_usage(lanes.db_path, "gemini_premium_text_calls", 1, "complex task graph")
    return reply


async def _subagent_response(lanes, text: str, memory_context: str, skill_context: str, task: dict[str, str], research: str) -> str:
    system = (
        f"You are Maya's {task['agent']}. Work only on this isolated subtask: {task['task']} "
        "Return concise findings, risks, and concrete recommendations. Do not make the final plan."
    )
    if not os.getenv("GOOGLE_API_KEY"):
        return f"No live model key. Subtask noted: {task['task']}"
    prompt = lanes._prompt(system, text, "\n\n".join(block for block in (memory_context, research) if block), skill_context)
    reply = await lanes.premium_sight.chat(prompt)
    await record_usage(lanes.db_path, "gemini_premium_text_calls", 1, f"complex {task['agent']}")
    return reply


async def _plan_agent(lanes, text: str, memory_context: str, skill_context: str, research: str, subagent_context: str = "") -> str:
    plan_prompt = lanes._prompt(
        MIND_ESCALATION_PROMPT + (
            "\nProduce a concise Codex-style plan only. Do not execute. "
            "Keep the final answer under 700 words so it fits Telegram. Finish every sentence. "
            "Use these sections only: Summary, Key Changes, Test Plan, Assumptions, Approval Needed. "
            "Use at most 5 bullets per section. If the request is self-heal, identify the concrete failure "
            "or missing evidence first; do not propose broad multi-system cleaning unless the evidence supports it."
        ),
        text,
        "\n\n".join(block for block in (memory_context, research, subagent_context) if block),
        skill_context,
    )
    return await lanes.mind.chat(plan_prompt, reasoning_effort=os.getenv("OPENAI_COMPLEX_REASONING_EFFORT", "medium"))


async def _review_plan(lanes, text: str, plan: str, memory_context: str, skill_context: str) -> str:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return "Steward review unavailable until the Claude key is added."
    prompt = lanes._prompt(
        "Review this GPT plan before implementation. Check hidden risks, missing assumptions, "
        "safety issues, overengineering, unclear tests, and practical gaps. Do not implement. "
        "Keep the review under 350 words. Start with PASS or REVISE. List only blocking or high-value issues.",
        f"Original request:\n{text}\n\nPlan to review:\n{plan}",
        _compact_block(memory_context, 7000),
        _compact_block(skill_context, 2500),
    )
    try:
        review = await lanes.steward.chat(prompt)
    except Exception as exc:
        return (
            "REVISE: Steward review unavailable because the Claude review provider failed. "
            f"Provider error: {type(exc).__name__}. Treat this plan as unreviewed and keep it proposal-only "
            "until a later review passes."
        )
    await record_usage(lanes.db_path, "claude_steward_calls", 1, "complex plan review")
    return review


def _compact_block(text: str, limit: int) -> str:
    clean = " ".join(str(text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[:limit].rsplit(" ", 1)[0].rstrip() + "\n[truncated for provider safety]"


def _wants_agentic_workflow(text: str) -> bool:
    from maya_core.complex_agentic_bridge import should_create_agentic_workflow

    return should_create_agentic_workflow(text)


def _merge_plan_review(plan: str, review: str, run_id: str = "", agentic_notice: str = "") -> str:
    workflow = f"\n\nWorkflow: {run_id}" if run_id else ""
    agentic = f"\n\n{agentic_notice.strip()}" if agentic_notice.strip() else ""
    return f"{plan.strip()}\n\nSteward review:\n{review.strip()}{workflow}{agentic}"
