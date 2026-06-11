from __future__ import annotations

from pathlib import Path
from typing import Literal

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

import asyncio

from browser_agent_state import task_type_for
from canonical_memory import upsert_canonical_memory
from domain_knowledge import domain_knowledge_context
from harness_state import HarnessState
from harness_artifact_store import record_structured_artifact
from harness_checkpoint_migration import snapshot_or_migrate
from harness_execution import execute_with_ledger
from harness_llm_planner import LlmCall, choose_next_action, plan_with_llm, verify_goal
from harness_observation_store import record_observation
from harness_store import create_approval, finish_run, record_artifact, record_event, upsert_run
from harness_tools import HarnessTools
from harness_workflows import classify_workflow, next_step_for, plan_for, workflow_for_action
from maya_permission_kernel import MayaPermissionKernel

# Budget for the opt-in agentic loop: hard ceiling on execute passes per run.
MAX_STEPS = 8

# Registry tools the loop can route through the existing workflow executors.
# Tools outside this map (and without an inline handler) fall back to the
# normal workflow execution for the original instruction.
_AGENTIC_TOOL_WORKFLOWS = {
    "browser.inspect": "browser",
    "browser.click": "browser",
    "screen.capture": "screen",
    "docx.create": "document",
    "xlsx.create": "document",
    "pptx.create": "document",
    "file.create": "document",
}


class HarnessGraphRunner:
    def __init__(self, db_path: str, planner_llm: LlmCall | None = None):
        self.db_path = db_path
        self.tools = HarnessTools(db_path)
        # Optional model hook (prompt -> response). When set and a run carries
        # agentic_loop=True, planning and goal verification become model-driven
        # and the graph may loop verify -> plan within the MAX_STEPS budget.
        self.planner_llm = planner_llm
        self.permission_kernel = MayaPermissionKernel()

    async def run(self, state: HarnessState) -> HarnessState:
        state["thread_id"] = state.get("thread_id") or f"harness:{state['run_id']}"
        async with AsyncSqliteSaver.from_conn_string(self.db_path) as saver:
            await saver.setup()
            graph = self._build_graph().compile(checkpointer=saver)
            result = await graph.ainvoke(
                state,
                config={"configurable": {"thread_id": state.get("thread_id") or "maya:shared"}},
            )
        return result

    async def resume(self, run: dict, user_text: str, approval_result: str = "") -> HarnessState:
        async with AsyncSqliteSaver.from_conn_string(self.db_path) as saver:
            await saver.setup()
            graph = self._build_graph().compile(checkpointer=saver)
            config = _config(str(run["thread_id"]))
            values = await snapshot_or_migrate(self.db_path, graph, config, run)
            pending = values.get("pending_approval") or {}
            resume_text = pending.get("action") if approval_result else user_text
            values.update({
                "user_text": resume_text or user_text,
                "last_user_instruction": user_text,
                "pending_approval": {} if approval_result else values.get("pending_approval", {}),
                "approval_result": approval_result,
                "user_turn_id": f"{run['run_id']}:{int(values.get('current_step') or 0) + 1}",
            })
            await graph.aupdate_state(config, values, as_node="finish")
            result = await graph.ainvoke(values, config=config)
        return result

    async def get_snapshot(self, run: dict) -> dict:
        async with AsyncSqliteSaver.from_conn_string(self.db_path) as saver:
            await saver.setup()
            graph = self._build_graph().compile(checkpointer=saver)
            config = _config(str(run["thread_id"]))
            values = await snapshot_or_migrate(self.db_path, graph, config, run)
        return values

    async def update_checkpoint(self, run: dict, values: dict) -> dict:
        async with AsyncSqliteSaver.from_conn_string(self.db_path) as saver:
            await saver.setup()
            graph = self._build_graph().compile(checkpointer=saver)
            config = _config(str(run["thread_id"]))
            state = await snapshot_or_migrate(self.db_path, graph, config, run)
            state.update(values)
            await graph.aupdate_state(config, state, as_node="finish")
        return state

    async def run_background_task(self, task: dict[str, str | int | None]) -> HarnessState:
        from harness_state import initial_harness_state

        task_id = int(task["id"])
        workflow_type = workflow_for_action(str(task["action_type"]))
        return await self.run(
            initial_harness_state(
                run_id=f"task_{task_id}",
                thread_id=f"harness:background:{task_id}",
                channel=str(task.get("channel") or "imac"),
                user_text=str(task.get("details") or task.get("title") or ""),
                workflow_type=workflow_type,
                goal=str(task.get("title") or ""),
            )
        )

    def _build_graph(self):
        graph = StateGraph(HarnessState)
        graph.add_node("ingest", self._ingest)
        graph.add_node("classify", self._classify)
        graph.add_node("plan", self._plan)
        graph.add_node("safety_check", self._safety_check)
        graph.add_node("execute", self._execute)
        graph.add_node("observe", self._observe)
        graph.add_node("verify", self._verify)
        graph.add_node("approval_gate", self._approval_gate)
        graph.add_node("memory_update", self._memory_update)
        graph.add_node("finish", self._finish)
        graph.add_node("fail", self._fail)
        graph.add_edge(START, "ingest")
        graph.add_edge("ingest", "classify")
        graph.add_edge("classify", "plan")
        graph.add_edge("plan", "safety_check")
        graph.add_edge("safety_check", "execute")
        graph.add_conditional_edges("execute", self._after_execute, {
            "approval": "approval_gate",
            "observe": "observe",
            "fail": "fail",
        })
        graph.add_edge("approval_gate", "finish")
        graph.add_edge("observe", "verify")
        graph.add_conditional_edges("verify", self._after_verify, {
            "continue": "plan",
            "finish": "memory_update",
            "fail": "fail",
        })
        graph.add_edge("memory_update", "finish")
        graph.add_edge("finish", END)
        graph.add_edge("fail", END)
        return graph

    async def _ingest(self, state: HarnessState) -> HarnessState:
        state["graph_status"] = "planning"
        state["last_user_instruction"] = state.get("user_text", "")
        await record_event(self.db_path, state["run_id"], "ingest", state.get("user_text", ""))
        await upsert_run(self.db_path, state)
        return state

    async def _classify(self, state: HarnessState) -> HarnessState:
        state["workflow_type"] = state.get("workflow_type") or classify_workflow(state.get("user_text", ""))
        await record_event(self.db_path, state["run_id"], "classify", state["workflow_type"])
        await record_event(self.db_path, state["run_id"], "subgraph", f"{state['workflow_type']}_subgraph")
        return state

    async def _plan(self, state: HarnessState) -> HarnessState:
        agentic = bool(state.get("agentic_loop")) and self.planner_llm is not None
        if agentic and int(state.get("current_step") or 0) > 0:
            await record_event(
                self.db_path,
                state["run_id"],
                "loop_iteration",
                f"step {int(state.get('current_step') or 0)} of {int(state.get('max_steps') or MAX_STEPS)}",
            )
        if agentic:
            if not state.get("plan"):
                state["plan"] = await plan_with_llm(dict(state), self.planner_llm)
            # Per-step domain retrieval: each loop pass re-queries the skill
            # knowledge bases with the current instruction, so multi-part
            # goals pull the recipe relevant to *this* step.
            step_text = state.get("last_user_instruction") or state.get("goal") or state.get("user_text", "")
            knowledge, domain_skill = await asyncio.to_thread(domain_knowledge_context, step_text)
            if domain_skill:
                await record_event(self.db_path, state["run_id"], "domain_knowledge", domain_skill.skill_id)
            state["planned_action"] = _forced_agentic_action(state) or await choose_next_action(dict(state), self.planner_llm, knowledge)
            await record_event(
                self.db_path,
                state["run_id"],
                "agentic_action",
                str(state["planned_action"].get("tool") or ("done" if state["planned_action"].get("done") else "unknown")),
            )
        elif not state.get("plan"):
            state["plan"] = plan_for(state.get("workflow_type", "general"))
        await record_event(self.db_path, state["run_id"], "plan", ", ".join(state["plan"]))
        return state

    async def _safety_check(self, state: HarnessState) -> HarnessState:
        state["graph_status"] = "verifying"
        await record_event(self.db_path, state["run_id"], "safety_check", "checked")
        return state

    async def _execute(self, state: HarnessState) -> HarnessState:
        state["graph_status"] = "executing"
        approved = state.get("approval_result") == "approved"
        agentic = bool(state.get("agentic_loop")) and self.planner_llm is not None
        action = dict(state.get("planned_action") or {})
        if agentic and action:
            handled = await self._execute_agentic_action(state, action, approved)
            if handled is not None:
                return handled
        result = await execute_with_ledger(self.db_path, self.tools, state, approved)
        state["final_response"] = result.message or _resume_message(state)
        state["current_step"] = int(state.get("current_step") or 0) + 1
        state["last_successful_step"] = result.next_step or state.get("workflow_type", "execute")
        state["next_suggested_step"] = next_step_for(state, result.keep_open)
        state["keep_open"] = result.keep_open
        state["model_lane"] = result.model_lane
        state["cost_recorded"] = result.cost_recorded
        if result.artifacts:
            state["artifacts"] = [*state.get("artifacts", []), *result.artifacts]
            if not result.structured_artifacts:
                for path in result.artifacts:
                    await record_artifact(self.db_path, state["run_id"], result.next_step, path)
        for artifact in result.structured_artifacts:
            await record_structured_artifact(self.db_path, state["run_id"], artifact)
        if result.observation:
            observation = result.observation.as_dict()
            state["last_observation"] = observation
            _carry_untrusted_state(state, observation)
            if state.get("workflow_type") == "browser":
                state["browser_state"] = _browser_state(state, observation)
            await record_observation(self.db_path, state["run_id"], result.observation)
        if result.requires_approval:
            state["graph_status"] = "waiting_approval"
            state["pending_approval"] = {"action": state.get("user_text", ""), "details": result.message}
        elif result.keep_open:
            state["graph_status"] = "waiting_user"
        if result.status == "skipped":
            state["last_error"] = "No harness tool handled this request."
        await record_event(self.db_path, state["run_id"], "execute", result.status)
        return state

    async def _execute_agentic_action(self, state: HarnessState, action: dict, approved: bool) -> HarnessState | None:
        """Consume the planner's chosen action. Returns the updated state when
        the action was fully handled here, or None to fall through to the
        normal workflow executor (with workflow/text possibly remapped)."""
        run_id = state["run_id"]
        if action.get("done"):
            answer = str(action.get("answer") or "").strip()
            state["final_response"] = answer or state.get("final_response") or "Goal reported complete by planner."
            state["current_step"] = int(state.get("current_step") or 0) + 1
            state["last_successful_step"] = "planner_done"
            state["next_suggested_step"] = "workflow complete"
            state["keep_open"] = False
            state["model_lane"] = "agentic planner"
            await record_event(self.db_path, run_id, "execute", "planner_done")
            return state
        tool_name = str(action.get("tool") or "").replace("_", ".", 1) if "." not in str(action.get("tool") or "") else str(action.get("tool"))
        args = dict(action.get("args") or {})
        decision = self.permission_kernel.check(
            tool_name,
            args=args,
            untrusted_influence=bool(state.get("untrusted_influence")),
            injection_detected=bool(state.get("injection_detected")),
        )
        if decision.decision == "deny":
            state["final_response"] = decision.reason
            state["current_step"] = int(state.get("current_step") or 0) + 1
            state["last_successful_step"] = "tool_denied"
            state["keep_open"] = False
            state["planned_action"] = {"done": True, "answer": decision.reason}
            await record_event(self.db_path, run_id, "tool_denied", f"{tool_name}: {decision.reason}")
            return state
        if decision.decision == "confirm" and not approved:
            state["pending_approval"] = {"action": tool_name, "details": str(args)[:500]}
            state["final_response"] = f"Approval required before {tool_name}."
            state["current_step"] = int(state.get("current_step") or 0) + 1
            state["graph_status"] = "waiting_approval"
            await record_event(self.db_path, run_id, "approval_required", tool_name)
            return state
        if tool_name == "memory.write":
            content = str(args.get("content") or "").strip()
            if content:
                memory_id = await upsert_canonical_memory(
                    self.db_path,
                    raw_text=content,
                    content=content,
                    kind=str(args.get("kind") or "lesson"),
                    scope=str(args.get("scope") or "global"),
                    source_channel="agentic_loop",
                    source_ref=run_id,
                    confidence="medium",
                )
                state["final_response"] = f"Recorded memory {memory_id}."
            else:
                state["final_response"] = "Planner asked to write memory without content; skipped."
            state["current_step"] = int(state.get("current_step") or 0) + 1
            state["last_successful_step"] = tool_name
            await record_event(self.db_path, run_id, "execute", f"agentic {tool_name}")
            return state
        if tool_name == "telegram.send_file":
            path = str(args.get("path") or "").strip()
            if path and Path(path).exists():
                state["final_response"] = f"Approved. I prepared the file for Telegram.\n[file:{path}]"
            elif path:
                state["final_response"] = f"I could not send the file because it no longer exists: {path}"
            else:
                state["final_response"] = "I could not send the file because no file path was provided."
            state["current_step"] = int(state.get("current_step") or 0) + 1
            state["last_successful_step"] = tool_name
            state["keep_open"] = False
            state["goal_satisfied"] = True
            await record_event(self.db_path, run_id, "execute", f"agentic {tool_name}")
            return state
        workflow = _AGENTIC_TOOL_WORKFLOWS.get(tool_name)
        if workflow:
            # Remap this pass to the matching workflow executor and fall through.
            state["workflow_type"] = workflow
            instruction = _agentic_tool_instruction(tool_name, args)
            if not instruction:
                instruction = str(
                    state.get("last_user_instruction")
                    or state.get("goal")
                    or state.get("user_text")
                    or ""
                ).strip()
            if instruction:
                state["user_text"] = instruction
            await record_event(self.db_path, run_id, "agentic_remap", f"{tool_name} -> {workflow}")
            return None
        await record_event(self.db_path, run_id, "tool_unmapped", tool_name)
        return None

    async def _observe(self, state: HarnessState) -> HarnessState:
        state["graph_status"] = "observing"
        note = state.get("final_response", "")[:400]
        state["observations"] = [*state.get("observations", []), note]
        await record_event(self.db_path, state["run_id"], "observe", note)
        return state

    async def _verify(self, state: HarnessState) -> HarnessState:
        state["graph_status"] = "verifying"
        ok = bool(state.get("final_response"))
        state["last_error"] = "" if ok else "No final response produced."
        if state.get("goal_satisfied"):
            state["goal_satisfied"] = True
        elif bool(state.get("agentic_loop")) and self.planner_llm is not None and ok:
            # Model-driven goal check: only an explicit NO keeps the loop open.
            state["goal_satisfied"] = await verify_goal(dict(state), self.planner_llm)
        else:
            # Without a planner the loop has no way to know it is unfinished,
            # so treat the goal as satisfied and keep single-pass behavior.
            state["goal_satisfied"] = True
        await record_event(self.db_path, state["run_id"], "verify", "passed" if ok else "failed")
        return state

    async def _approval_gate(self, state: HarnessState) -> HarnessState:
        pending = state.get("pending_approval") or {}
        await create_approval(self.db_path, state["run_id"], pending.get("action", ""), pending.get("details", ""))
        await upsert_run(self.db_path, state, status="paused")
        await record_event(self.db_path, state["run_id"], "approval_gate", "paused")
        return state

    async def _memory_update(self, state: HarnessState) -> HarnessState:
        if state.get("final_response"):
            state["memory_notes"] = [*state.get("memory_notes", []), state["final_response"][:240]]
        await record_event(self.db_path, state["run_id"], "memory_update", "noted")
        return state

    async def _finish(self, state: HarnessState) -> HarnessState:
        if state.get("pending_approval"):
            status = "paused"
        elif state.get("keep_open"):
            status = "running"
            state["graph_status"] = "waiting_user"
        else:
            status = "completed"
            state["graph_status"] = "completed"
            if _agentic_budget_exhausted(state):
                state["final_response"] = _budget_exhausted_message(state)
        await upsert_run(self.db_path, state, status=status)
        if status == "completed":
            await finish_run(self.db_path, state["run_id"])
        await record_event(self.db_path, state["run_id"], "finish", status)
        return state

    async def _fail(self, state: HarnessState) -> HarnessState:
        state["graph_status"] = "failed"
        await upsert_run(self.db_path, state, status="failed")
        await record_event(self.db_path, state["run_id"], "fail", state.get("last_error", "failed"))
        return state

    @staticmethod
    def _after_execute(state: HarnessState) -> Literal["approval", "observe", "fail"]:
        if state.get("pending_approval"):
            return "approval"
        if state.get("last_error"):
            return "fail"
        return "observe"

    @staticmethod
    def _after_verify(state: HarnessState) -> Literal["continue", "finish", "fail"]:
        if state.get("last_error"):
            return "fail"
        if not state.get("agentic_loop"):
            return "finish"
        if state.get("keep_open") or state.get("pending_approval"):
            return "finish"
        budget = int(state.get("max_steps") or MAX_STEPS)
        if state.get("goal_satisfied") or int(state.get("current_step") or 0) >= budget:
            return "finish"
        return "continue"


def _resume_message(state: HarnessState) -> str:
    plan = state.get("plan") or []
    step = int(state.get("current_step") or 0)
    if plan:
        return f"I still have this workflow open: {state.get('goal', '')}. Last step: {plan[min(step, len(plan)-1)]}."
    return f"I still have this workflow open: {state.get('goal', '')}."


def _agentic_tool_instruction(tool_name: str, args: dict) -> str:
    if tool_name == "browser.click":
        target = str(args.get("target") or args.get("label") or args.get("text") or "").strip()
        if target:
            return target if target.lower().startswith(("click ", "choose ", "select ", "press ")) else f"click {target}"
    if tool_name == "docx.create":
        topic = str(args.get("topic") or args.get("title") or args.get("content") or "").strip()
        if topic:
            return topic if topic.lower().startswith(("write ", "make ", "create ")) else f"write a Word document about {topic}"
    return " ".join(str(v) for v in args.values() if isinstance(v, str)).strip()


def _forced_agentic_action(state: HarnessState) -> dict | None:
    goal = str(state.get("goal") or state.get("user_text") or "")
    if not _goal_requests_telegram_file(goal):
        return None
    artifacts = [str(item) for item in state.get("artifacts") or [] if str(item)]
    if artifacts:
        return {"tool": "telegram.send_file", "args": {"path": artifacts[-1]}}
    observation = dict(state.get("last_observation") or {})
    if int(state.get("current_step") or 0) < 2 or not observation.get("text_summary"):
        return None
    topic = _summary_doc_topic(goal, observation)
    return {"tool": "docx.create", "args": {"topic": topic}}


def _goal_requests_telegram_file(goal: str) -> bool:
    lowered = goal.lower()
    return "telegram" in lowered and any(word in lowered for word in ("send", "share", "attach")) and any(
        word in lowered for word in ("file", "document", "doc", "summary")
    )


def _summary_doc_topic(goal: str, observation: dict) -> str:
    context = str(observation.get("text_summary") or "").strip()
    return (
        "a concise source-grounded summary file for this request: "
        f"{goal}. Use this browser evidence and do not add unsupported facts: {context[:2200]}"
    )


def _agentic_budget_exhausted(state: HarnessState) -> bool:
    if not state.get("agentic_loop") or state.get("goal_satisfied"):
        return False
    budget = int(state.get("max_steps") or MAX_STEPS)
    return int(state.get("current_step") or 0) >= budget


def _budget_exhausted_message(state: HarnessState) -> str:
    budget = int(state.get("max_steps") or MAX_STEPS)
    previous = str(state.get("final_response") or "").strip()
    if len(previous) > 900:
        previous = previous[:897].rstrip() + "..."
    if previous:
        return (
            f"I reached the {budget}-step agentic budget before I could verify the full goal. "
            f"Last useful result:\n{previous}"
        )
    return f"I reached the {budget}-step agentic budget before I could verify the full goal."


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _carry_untrusted_state(state: HarnessState, observation: dict) -> None:
    if not observation.get("untrusted_influence"):
        return
    state["untrusted_influence"] = True
    state["injection_detected"] = bool(state.get("injection_detected") or observation.get("injection_detected"))
    notes = list(state.get("untrusted_signals") or [])
    for note in observation.get("untrusted_signals") or []:
        text = str(note)
        if text and text not in notes:
            notes.append(text)
    state["untrusted_signals"] = notes[-12:]
    source = observation.get("untrusted_source") or observation.get("source") or ""
    if source:
        state["untrusted_source"] = source


def _browser_state(state: HarnessState, observation: dict) -> dict:
    previous = dict(state.get("browser_state") or {})
    steps = list(previous.get("steps") or [])
    if state.get("last_successful_step"):
        steps.append(str(state["last_successful_step"]))
    previous.update({
        "goal": state.get("goal") or state.get("user_text", ""),
        "task_type": task_type_for(state.get("goal") or state.get("user_text", "")),
        "current_url": observation.get("url", ""),
        "page_title": observation.get("page_title", ""),
        "search_query": state.get("user_text", ""),
        "last_observation_id": observation.get("text_hash", ""),
        "confidence": observation.get("confidence", 0),
        "steps": steps[-12:],
    })
    return previous
