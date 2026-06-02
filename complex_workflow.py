from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Awaitable, Callable

from harness_store import finish_run, latest_events, new_run_id, record_event, upsert_run


AgentCall = Callable[[], Awaitable[str]]


@dataclass(frozen=True)
class ComplexWorkflowResult:
    run_id: str
    plan: str
    review: str
    graph: list[dict[str, str]]
    subagent_outputs: dict[str, str]
    research: str = ""


async def run_complex_plan_workflow(
    db_path: str | None,
    request: str,
    *,
    research_agent: AgentCall,
    graph_planner_agent: Callable[[str], Awaitable[str]],
    subagent_runner: Callable[[dict[str, str], str], Awaitable[str]],
    planner_agent: Callable[[str, str], Awaitable[str]],
    reviewer_agent: Callable[[str, str, str], Awaitable[str]],
) -> ComplexWorkflowResult:
    run_id = new_run_id()
    await _start(db_path, run_id, request)
    research = ""
    plan = ""
    review = ""
    graph: list[dict[str, str]] = []
    subagent_outputs: dict[str, str] = {}
    try:
        research = await _run_agent(db_path, run_id, "research_agent", research_agent)
        graph_text = await _run_agent(db_path, run_id, "graph_planner_agent", lambda: graph_planner_agent(research))
        graph = _parse_task_graph(graph_text)
        await _event(db_path, run_id, "task_graph_ready", _graph_summary(graph))
        subagent_outputs = await _run_subagents(db_path, run_id, graph, research, subagent_runner)
        merged_context = _merge_subagent_outputs(subagent_outputs)
        plan = await _run_agent(db_path, run_id, "planner_agent", lambda: planner_agent(research, merged_context))
        review = await _run_agent(db_path, run_id, "review_agent", lambda: reviewer_agent(plan, research, merged_context))
        await _finish(db_path, run_id, "completed")
    except Exception as exc:
        await _event(db_path, run_id, "workflow_failed", f"{type(exc).__name__}: {exc}")
        await _finish(db_path, run_id, "failed")
        raise
    return ComplexWorkflowResult(run_id=run_id, research=research, plan=plan, review=review, graph=graph, subagent_outputs=subagent_outputs)


async def complex_workflow_status(db_path: str, run_id: str) -> str:
    events = await latest_events(db_path, run_id, limit=24)
    if not events:
        return f"Complex workflow: {run_id}"
    lines = [f"Complex workflow: {run_id}"]
    for index, event in enumerate(events, start=1):
        lines.append(f"{index}) {event['event']}: {event['details']}")
    return "\n".join(lines)


async def _start(db_path: str | None, run_id: str, request: str) -> None:
    if not db_path:
        return
    await upsert_run(
        db_path,
        {
            "run_id": run_id,
            "thread_id": "maya:complex",
            "channel": "shared",
            "workflow_type": "complex",
            "goal": request[:500],
            "current_step": 0,
            "agents": ["research_agent", "graph_planner_agent", "parallel_subagents", "planner_agent", "review_agent"],
        },
    )
    await record_event(db_path, run_id, "workflow_started", "complex workflow with bounded dynamic task graph")


async def _run_agent(db_path: str | None, run_id: str, name: str, call: AgentCall) -> str:
    await _event(db_path, run_id, f"{name}_started", "running")
    output = await call()
    summary = " ".join(output.strip().split())[:700] if output.strip() else "no output"
    await _event(db_path, run_id, f"{name}_finished", summary)
    return output


async def _run_subagents(
    db_path: str | None,
    run_id: str,
    graph: list[dict[str, str]],
    research: str,
    subagent_runner: Callable[[dict[str, str], str], Awaitable[str]],
) -> dict[str, str]:
    if not graph:
        return {}
    await _event(db_path, run_id, "parallel_subagents_started", _graph_summary(graph))
    results = await asyncio.gather(*(_run_one_subagent(db_path, run_id, task, research, subagent_runner) for task in graph))
    outputs = {name: output for name, output in results}
    await _event(db_path, run_id, "parallel_subagents_finished", f"{len(outputs)} subagent result(s)")
    return outputs


async def _run_one_subagent(
    db_path: str | None,
    run_id: str,
    task: dict[str, str],
    research: str,
    subagent_runner: Callable[[dict[str, str], str], Awaitable[str]],
) -> tuple[str, str]:
    name = _safe_agent_name(task.get("agent") or "subagent")
    await _event(db_path, run_id, f"{name}_started", task.get("task", "running")[:700])
    output = await subagent_runner(task, research)
    summary = " ".join(output.strip().split())[:700] if output.strip() else "no output"
    await _event(db_path, run_id, f"{name}_finished", summary)
    return name, output


def _parse_task_graph(text: str) -> list[dict[str, str]]:
    blob = _json_blob(text)
    if not blob:
        return _fallback_graph()
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        return _fallback_graph()
    if isinstance(data, dict):
        data = data.get("tasks", [])
    if not isinstance(data, list):
        return _fallback_graph()
    graph: list[dict[str, str]] = []
    for item in data[:4]:
        if not isinstance(item, dict):
            continue
        agent = _safe_agent_name(str(item.get("agent") or item.get("name") or "analysis_agent"))
        task = " ".join(str(item.get("task") or item.get("goal") or "").split())[:500]
        if task:
            graph.append({"agent": agent, "task": task})
    return graph or _fallback_graph()


def _json_blob(text: str) -> str:
    match = re.search(r"\[[\s\S]*\]|\{[\s\S]*\}", text.strip())
    return match.group(0) if match else ""


def _fallback_graph() -> list[dict[str, str]]:
    return [
        {"agent": "risk_agent", "task": "Identify risks, weak assumptions, and failure modes."},
        {"agent": "implementation_agent", "task": "Identify implementation steps and dependencies."},
        {"agent": "test_agent", "task": "Identify practical verification and regression tests."},
    ]


def _merge_subagent_outputs(outputs: dict[str, str]) -> str:
    if not outputs:
        return ""
    return "\n\n".join(f"{name}:\n{output.strip()}" for name, output in outputs.items())


def _graph_summary(graph: list[dict[str, str]]) -> str:
    return "; ".join(f"{item['agent']}: {item['task']}" for item in graph)[:900]


def _safe_agent_name(value: str) -> str:
    name = re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_")
    return name[:40] or "subagent"


async def _event(db_path: str | None, run_id: str, event: str, details: str) -> None:
    if db_path:
        await record_event(db_path, run_id, event, details)


async def _finish(db_path: str | None, run_id: str, status: str) -> None:
    if db_path:
        await finish_run(db_path, run_id, status=status)
