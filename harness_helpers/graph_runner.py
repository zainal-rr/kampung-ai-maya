from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Mapping

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

import asyncio
import re

from maya_browser.browser_agent_state import task_type_for
from maya_memory.canonical_memory import upsert_canonical_memory
from maya_core.domain_knowledge import domain_knowledge_context
from maya_documents.artifact_naming import named_artifact_path
from maya_documents.office_files import create_docx, create_xlsx, safe_slug, spreadsheet_rows
from maya_harness.harness_state import HarnessState
from maya_harness.harness_artifact_store import record_structured_artifact
from maya_harness.harness_checkpoint_migration import snapshot_or_migrate
from maya_harness.harness_execution import execute_with_ledger
from maya_harness.harness_llm_planner import LlmCall, choose_next_action, plan_with_llm, synthesize_final_answer, verify_goal
from maya_harness.harness_models import local_artifact
from maya_harness.harness_observation_store import record_observation
from maya_harness.metacognition import (
    ReflectionDecision,
    action_shape,
    append_reflection,
    classify_tool_result,
    should_block_repeated_action,
    should_stop_for_no_progress,
)
from maya_harness.pattern_recognition import record_pattern_from_episode, retrieve_pattern_facts
from maya_harness.planner_facts import append_pattern_facts, append_planner_fact
from maya_harness.harness_store import create_approval, finish_run, record_artifact, record_event, upsert_run
from maya_harness.harness_tools import HarnessTools
from maya_harness.harness_workflows import classify_workflow, next_step_for, plan_for, workflow_for_action
from maya_core.maya_permission_kernel import MayaPermissionKernel
from maya_core.safe_paths import resolve_safe_path
from maya_core.workspace_paths import is_workspace_path, workspace_dir

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
        from maya_harness.harness_state import initial_harness_state

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
            pattern_facts = await retrieve_pattern_facts(self.db_path, state)
            append_pattern_facts(state, pattern_facts)
            if pattern_facts:
                await record_event(self.db_path, state["run_id"], "pattern_recognition", f"{len(pattern_facts)} hint(s)")
            if not state.get("plan"):
                state["plan"] = await plan_with_llm(dict(state), self.planner_llm)
            # Per-step domain retrieval: each loop pass re-queries the skill
            # knowledge bases with the current instruction, so multi-part
            # goals pull the recipe relevant to *this* step.
            step_text = state.get("last_user_instruction") or state.get("goal") or state.get("user_text", "")
            knowledge, domain_skill = await asyncio.to_thread(domain_knowledge_context, step_text)
            if domain_skill:
                await record_event(self.db_path, state["run_id"], "domain_knowledge", domain_skill.skill_id)
            forced = _forced_agentic_action(state)
            if forced is None and _at_synthesis_reserve(state):
                # Synthesis reserve (Phase 6 finding 2026-06-12): the final
                # budget step is not the planner's to spend on more gathering.
                # Whatever evidence exists, the loop lands a real answer now.
                answer = await synthesize_final_answer(dict(state), self.planner_llm, knowledge)
                if answer:
                    forced = {"done": True, "answer": answer}
                    state["forced_synthesis"] = True
                    await record_event(
                        self.db_path,
                        state["run_id"],
                        "synthesis_reserve",
                        f"step {int(state.get('current_step') or 0) + 1} of {int(state.get('max_steps') or MAX_STEPS)}",
                    )
            state["planned_action"] = forced or await choose_next_action(dict(state), self.planner_llm, knowledge)
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
            append_planner_fact(state, observation)
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
        shape = _planned_action_shape(state)
        decision = append_reflection(
            state,
            classify_tool_result(
                status=result.status,
                message=result.message,
                requires_approval=result.requires_approval,
                args_shape=shape,
            ),
        )
        await record_event(self.db_path, state["run_id"], "metacognition", f"{decision.failure_code}:{decision.reflection_move}")
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
        repeated = should_block_repeated_action(state, tool_name, args)
        if repeated is not None:
            append_reflection(state, repeated)
            state["final_response"] = (
                "I stopped because the same action shape already failed twice. "
                "I do not want to loop or pretend it worked."
            )
            state["current_step"] = int(state.get("current_step") or 0) + 1
            state["last_successful_step"] = "metacognition_stop"
            state["keep_open"] = False
            state["metacognition_stop_reason"] = repeated.failure_code
            await record_event(self.db_path, run_id, "metacognition_stop", repeated.rationale)
            return state
        shape = action_shape(tool_name, args)
        args, field_provenance = _trusted_agentic_artifact_args(state, tool_name, args)
        skip_permission_for_bad_args = tool_name == "memory.write" and not str(args.get("content") or "").strip()
        if not skip_permission_for_bad_args:
            decision = self.permission_kernel.check(
                tool_name,
                args=args,
                field_provenance=field_provenance,
                untrusted_influence=bool(state.get("untrusted_influence")),
                injection_detected=bool(state.get("injection_detected")),
            )
            await record_event(
                self.db_path,
                run_id,
                "permission_decision",
                f"{tool_name}: {decision.decision}: {decision.reason}",
            )
            if decision.decision == "deny":
                reflection = append_reflection(
                    state,
                    ReflectionDecision("gate_blocked", 0.95, "high", "stop_honestly", shape, decision.reason),
                )
                state["final_response"] = decision.reason
                state["current_step"] = int(state.get("current_step") or 0) + 1
                state["last_successful_step"] = "tool_denied"
                state["keep_open"] = False
                state["planned_action"] = {"done": True, "answer": decision.reason}
                await record_event(self.db_path, run_id, "metacognition", f"{reflection.failure_code}:{reflection.reflection_move}")
                await record_event(self.db_path, run_id, "tool_denied", f"{tool_name}: {decision.reason}")
                return state
            if decision.decision == "confirm" and not approved:
                reflection = append_reflection(
                    state,
                    ReflectionDecision("gate_blocked", 0.95, "high", "ask_owner", shape, f"Approval required for {tool_name}."),
                )
                state["pending_approval"] = {"action": tool_name, "details": str(args)[:500]}
                state["final_response"] = f"Approval required before {tool_name}."
                state["current_step"] = int(state.get("current_step") or 0) + 1
                state["graph_status"] = "waiting_approval"
                await record_event(self.db_path, run_id, "metacognition", f"{reflection.failure_code}:{reflection.reflection_move}")
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
                reflection = append_reflection(
                    state,
                    ReflectionDecision("progressed", 0.75, "medium", "continue_same_plan", shape, "Memory write completed."),
                )
            else:
                state["final_response"] = "Planner asked to write memory without content; skipped."
                reflection = append_reflection(
                    state,
                    ReflectionDecision("bad_args", 0.9, "high", "retry_same_step", shape, "memory.write had no content."),
                )
            state["current_step"] = int(state.get("current_step") or 0) + 1
            state["last_successful_step"] = tool_name
            await record_event(self.db_path, run_id, "metacognition", f"{reflection.failure_code}:{reflection.reflection_move}")
            await record_event(self.db_path, run_id, "execute", f"agentic {tool_name}")
            return state
        if tool_name == "telegram.send_file":
            path = str(args.get("path") or "").strip()
            if path and Path(path).exists():
                state["final_response"] = f"Approved. I prepared the file for Telegram.\n[file:{path}]"
                reflection = append_reflection(
                    state,
                    ReflectionDecision("progressed", 0.75, "medium", "continue_same_plan", shape, "File was prepared for Telegram."),
                )
            elif path:
                state["final_response"] = f"I could not send the file because it no longer exists: {path}"
                reflection = append_reflection(
                    state,
                    ReflectionDecision("qa_failed", 0.9, "high", "repair_output", shape, "Requested file no longer exists."),
                )
            else:
                state["final_response"] = "I could not send the file because no file path was provided."
                reflection = append_reflection(
                    state,
                    ReflectionDecision("bad_args", 0.9, "high", "retry_same_step", shape, "telegram.send_file had no path."),
                )
            state["current_step"] = int(state.get("current_step") or 0) + 1
            state["last_successful_step"] = tool_name
            state["keep_open"] = False
            state["goal_satisfied"] = True
            await record_event(self.db_path, run_id, "metacognition", f"{reflection.failure_code}:{reflection.reflection_move}")
            await record_event(self.db_path, run_id, "execute", f"agentic {tool_name}")
            return state
        if tool_name in {"file.create", "docx.create", "xlsx.create"}:
            return await _execute_agentic_artifact_fast_path(
                self.db_path,
                state,
                tool_name,
                args,
                field_provenance,
                shape,
            )
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
        reflection = append_reflection(
            state,
            ReflectionDecision("wrong_tool", 0.9, "high", "choose_different_tool", shape, f"{tool_name} is not mapped."),
        )
        await record_event(self.db_path, run_id, "metacognition", f"{reflection.failure_code}:{reflection.reflection_move}")
        await record_event(self.db_path, run_id, "tool_unmapped", tool_name)
        return None

    async def _observe(self, state: HarnessState) -> HarnessState:
        state["graph_status"] = "observing"
        note = state.get("final_response", "")[:400]
        previous = [*state.get("observations", [])]
        state["observations"] = [*previous, note]
        if note and previous and note == previous[-1]:
            decision = append_reflection(
                state,
                ReflectionDecision("no_progress", 0.75, "medium", "choose_different_tool", _planned_action_shape(state), "Latest result repeated the previous observation."),
            )
            await record_event(self.db_path, state["run_id"], "metacognition", f"{decision.failure_code}:{decision.reflection_move}")
        elif note:
            state["no_progress_count"] = 0
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
        if (
            bool(state.get("agentic_loop"))
            and self.planner_llm is not None
            and not state.get("goal_satisfied")
            and should_stop_for_no_progress(state)
        ):
            state["metacognition_stop_reason"] = "no_progress"
            state["final_response"] = (
                "I stopped because multiple steps made no progress. "
                "I do not want to keep looping or claim success without evidence."
            )
            state["keep_open"] = False
            await record_event(self.db_path, state["run_id"], "metacognition_stop", "no_progress")
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
            if _agentic_budget_exhausted(state) and not state.get("forced_synthesis"):
                # The generic budget message is the fallback for runs that hit
                # the cap WITHOUT a synthesized answer. A reserved-step
                # synthesis already carries its own evidence-gap honesty and
                # must not be clobbered.
                state["final_response"] = _budget_exhausted_message(state)
        await upsert_run(self.db_path, state, status=status)
        if status == "completed":
            pattern_id = await record_pattern_from_episode(self.db_path, state)
            if pattern_id:
                await record_event(self.db_path, state["run_id"], "pattern_store", pattern_id)
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
        if state.get("metacognition_stop_reason"):
            return "finish"
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
    if tool_name == "file.create":
        path = str(args.get("path") or args.get("output_path") or args.get("destination_path") or "").strip()
        content = str(args.get("content") or args.get("body") or args.get("text") or "").strip()
        if path and content:
            return f"create file {path} with {content}"
    if tool_name == "docx.create":
        topic = str(args.get("topic") or args.get("title") or args.get("content") or "").strip()
        if topic:
            return topic if topic.lower().startswith(("write ", "make ", "create ")) else f"write a Word document about {topic}"
    if tool_name == "xlsx.create":
        topic = str(args.get("topic") or args.get("title") or args.get("content") or "").strip()
        if topic:
            return topic if topic.lower().startswith(("make ", "create ")) else f"create a spreadsheet about {topic}"
    return " ".join(str(v) for v in args.values() if isinstance(v, str)).strip()


async def _execute_agentic_artifact_fast_path(
    db_path: str,
    state: HarnessState,
    tool_name: str,
    args: Mapping[str, Any],
    field_provenance: Mapping[str, str],
    shape: str,
) -> HarnessState:
    run_id = state["run_id"]
    path = _allowed_fast_artifact_path(args, field_provenance)
    if path is None:
        message = f"I could not create the local artifact because {tool_name} did not have a trusted Maya workspace path."
        reflection = append_reflection(
            state,
            ReflectionDecision("bad_args", 0.9, "high", "retry_same_step", shape, message),
        )
        state["final_response"] = message
        state["current_step"] = int(state.get("current_step") or 0) + 1
        state["last_successful_step"] = "artifact_fast_path_blocked"
        await record_event(db_path, run_id, "metacognition", f"{reflection.failure_code}:{reflection.reflection_move}")
        await record_event(db_path, run_id, "agentic_artifact_fast_path", f"{tool_name}: blocked: untrusted or missing path")
        await record_event(db_path, run_id, "execute", "artifact_fast_path_blocked")
        return state

    try:
        if tool_name == "file.create":
            create_variant = _file_create_variant(state, args)
            if create_variant in {"folder", "project"}:
                await asyncio.to_thread(_make_fast_local_directory, path)
                kind = create_variant
                summary = f"local {create_variant} folder created by agentic artifact fast path"
            else:
                await asyncio.to_thread(_write_fast_local_file, path, _artifact_body(args, state))
                kind = _kind_for_fast_artifact(path, "note")
                summary = "local file created by agentic artifact fast path"
        elif tool_name == "docx.create":
            topic = _artifact_topic(args, state)
            await asyncio.to_thread(create_docx, path, _artifact_title(topic), _docx_sections(topic, args, state))
            kind = "document"
            summary = f"Word document draft: {_artifact_title(topic)}"
        elif tool_name == "xlsx.create":
            topic = _artifact_topic(args, state)
            headers, rows = _xlsx_fast_rows(topic, args)
            await asyncio.to_thread(create_xlsx, path, _artifact_title(topic), headers, rows)
            kind = "spreadsheet"
            summary = f"Spreadsheet draft: {_artifact_title(topic)}"
        else:  # defensive; caller only uses the three tools above.
            raise ValueError(f"unsupported fast artifact tool: {tool_name}")
    except Exception as exc:  # noqa: BLE001 - report honestly into the agentic trace.
        message = f"I could not create the local artifact: {type(exc).__name__}: {exc}"
        reflection = append_reflection(
            state,
            ReflectionDecision("tool_error", 0.9, "high", "repair_output", shape, message),
        )
        state["final_response"] = message
        state["current_step"] = int(state.get("current_step") or 0) + 1
        state["last_successful_step"] = "artifact_fast_path_error"
        await record_event(db_path, run_id, "metacognition", f"{reflection.failure_code}:{reflection.reflection_move}")
        await record_event(db_path, run_id, "agentic_artifact_fast_path", f"{tool_name}: error: {type(exc).__name__}")
        await record_event(db_path, run_id, "execute", "artifact_fast_path_error")
        return state

    artifact = local_artifact(kind, str(path), summary, "agentic_artifact_fast_path")
    await record_structured_artifact(db_path, run_id, artifact)
    state["final_response"] = f"Done. I created the local artifact at {path}.\n[file:{path}]"
    state["artifacts"] = [*state.get("artifacts", []), str(path)]
    state["current_step"] = int(state.get("current_step") or 0) + 1
    state["last_successful_step"] = tool_name
    state["next_suggested_step"] = "verify artifact"
    state["keep_open"] = False
    state["goal_satisfied"] = True
    reflection = append_reflection(
        state,
        ReflectionDecision("progressed", 0.8, "medium", "continue_same_plan", shape, f"{tool_name} created {path}."),
    )
    await record_event(db_path, run_id, "metacognition", f"{reflection.failure_code}:{reflection.reflection_move}")
    await record_event(db_path, run_id, "agentic_artifact_fast_path", f"{tool_name}: {path}")
    await record_event(db_path, run_id, "execute", f"agentic {tool_name}")
    return state


def _allowed_fast_artifact_path(args: Mapping[str, Any], field_provenance: Mapping[str, str]) -> Path | None:
    raw = str(args.get("path") or args.get("output_path") or args.get("destination_path") or "").strip()
    if not raw:
        return None
    if not any(field_provenance.get(field) == "maya_derived" for field in ("path", "output_path", "destination_path")):
        return None
    decision = resolve_safe_path(raw, "write")
    if not decision.allowed or not decision.resolved:
        return None
    if not is_workspace_path(decision.resolved):
        return None
    if decision.resolved.exists():
        return None
    return decision.resolved


def _write_fast_local_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_fast_local_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=False)


def _artifact_topic(args: Mapping[str, Any], state: Mapping[str, Any]) -> str:
    for key in ("topic", "title", "name", "filename", "file_name"):
        value = str(args.get(key) or "").strip()
        if value:
            return value
    for key in ("content", "body", "text"):
        value = str(args.get(key) or "").strip()
        if value:
            return value[:180]
    return str(state.get("goal") or state.get("last_user_instruction") or state.get("user_text") or "Maya local artifact").strip()


def _artifact_title(topic: str) -> str:
    title = " ".join(str(topic or "Maya Local Artifact").split()).strip()
    if len(title) > 90:
        title = title[:87].rstrip() + "..."
    return title or "Maya Local Artifact"


def _artifact_body(args: Mapping[str, Any], state: Mapping[str, Any]) -> str:
    for key in ("content", "body", "text"):
        value = str(args.get(key) or "").strip()
        if value:
            return value
    topic = _artifact_topic(args, state)
    return (
        f"# {_artifact_title(topic)}\n\n"
        "- Draft created by Maya.\n"
        "- Review and edit this local artifact as needed.\n"
        f"- Source task: {str(state.get('goal') or state.get('user_text') or topic)[:300]}\n"
    )


def _docx_sections(topic: str, args: Mapping[str, Any], state: Mapping[str, Any]) -> list[tuple[str, list[str]]]:
    body = _artifact_body(args, state)
    lines = [line.strip(" -*\t") for line in body.splitlines() if line.strip()]
    if not lines:
        lines = [f"Draft notes for {_artifact_title(topic)}.", "Review and expand as needed."]
    return [
        ("Summary", lines[:6]),
        ("Next Steps", ["Review the draft.", "Add any missing specifics.", "Keep this as a local reversible artifact."]),
    ]


def _xlsx_fast_rows(topic: str, args: Mapping[str, Any]) -> tuple[list[str], list[list[str]]]:
    headers = args.get("headers")
    rows = args.get("rows")
    if isinstance(headers, list) and all(isinstance(item, str) for item in headers):
        safe_headers = [str(item)[:80] for item in headers[:12]]
        if isinstance(rows, list):
            safe_rows = [
                [str(cell)[:240] for cell in row[: len(safe_headers)]]
                for row in rows[:50]
                if isinstance(row, list)
            ]
            if safe_headers and safe_rows:
                return safe_headers, safe_rows
    return spreadsheet_rows(topic)


def _kind_for_fast_artifact(path: Path, fallback: str) -> str:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return "document"
    if suffix == ".xlsx":
        return "spreadsheet"
    if suffix in {".md", ".txt"}:
        return "note"
    return fallback


def _trusted_agentic_artifact_args(
    state: Mapping[str, Any],
    tool_name: str,
    args: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    """Attach field provenance from the harness-owned channel only.

    Planner-supplied ``*_source`` fields are intentionally ignored. A field is
    trusted only when the harness can independently derive/normalize it from
    owner-visible state and Maya's safe-path policy.
    """
    normalized = dict(args)
    field_provenance: dict[str, str] = {}
    file_variant = _file_create_variant(state, normalized) if tool_name == "file.create" else ""
    if tool_name in {"file.create", "docx.create", "xlsx.create"} and not _has_path_control_value(normalized):
        derived = _derive_agentic_artifact_path(state, tool_name, normalized)
        if derived:
            normalized["path"] = derived
            field_provenance["path"] = "maya_derived"
    if tool_name == "file.create":
        for field in ("path", "output_path", "destination_path"):
            if field not in normalized:
                continue
            trusted = _trusted_agentic_file_path(state, normalized[field], file_variant)
            if trusted:
                normalized[field] = trusted
                field_provenance[field] = "maya_derived"
    if tool_name in {"file.create", "docx.create", "xlsx.create"}:
        for field in ("filename", "file_name", "name", "title"):
            value = normalized.get(field)
            if _owner_instruction_contains_value(state, value) and _safe_local_control_name(value):
                field_provenance[field] = "maya_derived"
    if tool_name == "xlsx.create":
        for field in ("sheet_name", "tab_name", "worksheet_name"):
            value = normalized.get(field)
            if _owner_instruction_contains_value(state, value) and _safe_sheet_control_name(value):
                field_provenance[field] = "owner_text"
    return normalized, field_provenance


def _has_path_control_value(args: Mapping[str, Any]) -> bool:
    return any(str(args.get(field) or "").strip() for field in ("path", "output_path", "destination_path"))


def _derive_agentic_artifact_path(state: Mapping[str, Any], tool_name: str, args: Mapping[str, Any]) -> str:
    if any(_truthy(args.get(field)) for field in ("recipient", "to", "send_to", "share_with", "upload_to", "delivery_target", "disclose_to")):
        return ""
    topic = _artifact_topic(args, state)
    if tool_name == "file.create":
        variant = _file_create_variant(state, args)
        if variant in {"folder", "project"}:
            base = workspace_dir("Projects" if variant == "project" else "notes")
            candidate = _versioned_directory(base / safe_slug(topic, max_length=60))
            decision = resolve_safe_path(candidate, "write")
            if not decision.allowed or not decision.resolved:
                return ""
            if not is_workspace_path(decision.resolved):
                return ""
            if decision.resolved.exists():
                return ""
            return str(decision.resolved)
    folder, suffix = {
        "file.create": ("notes", "md"),
        "docx.create": ("documents", "docx"),
        "xlsx.create": ("spreadsheets", "xlsx"),
    }.get(tool_name, ("artifacts", "txt"))
    candidate = named_artifact_path(workspace_dir(folder), topic, suffix)
    decision = resolve_safe_path(candidate, "write")
    if not decision.allowed or not decision.resolved:
        return ""
    if not is_workspace_path(decision.resolved):
        return ""
    if decision.resolved.exists():
        return ""
    return str(decision.resolved)


def _trusted_agentic_file_path(state: Mapping[str, Any], raw: Any, variant: str = "") -> str:
    text = str(raw or "").strip().strip("\"'")
    if not text or "\x00" in text:
        return ""
    if not _owner_instruction_contains_path(state, text):
        return ""
    candidate = Path(text).expanduser()
    if not candidate.is_absolute():
        if _simple_relative_name(candidate):
            if variant in {"folder", "project"}:
                candidate = workspace_dir("Projects" if variant == "project" else "notes") / safe_slug(text, max_length=60)
            elif not candidate.suffix:
                candidate = workspace_dir("notes") / f"{safe_slug(text, max_length=60)}.md"
            else:
                candidate = workspace_dir("notes") / candidate
        else:
            candidate = workspace_dir("") / candidate
    decision = resolve_safe_path(candidate, "write")
    if not decision.allowed or not decision.resolved:
        return ""
    if not is_workspace_path(decision.resolved):
        return ""
    if decision.resolved.exists():
        return ""
    return str(decision.resolved)


def _owner_instruction_contains_path(state: Mapping[str, Any], raw: str) -> bool:
    needle = " ".join(str(raw or "").strip().strip("\"'").split()).lower()
    if not needle:
        return False
    owner_text = _owner_instruction_text(state)
    if needle in owner_text:
        return True
    name = Path(needle).name
    return bool(name and (name in owner_text or _control_tokens_match_owner(name, owner_text)))


def _owner_instruction_contains_value(state: Mapping[str, Any], raw: Any) -> bool:
    value = " ".join(str(raw or "").strip().split()).lower()
    owner_text = _owner_instruction_text(state)
    return bool(value and (value in owner_text or _control_tokens_match_owner(value, owner_text)))


def _owner_instruction_text(state: Mapping[str, Any]) -> str:
    parts = [
        str(state.get("goal") or ""),
        str(state.get("last_user_instruction") or ""),
        str(state.get("user_text") or ""),
    ]
    return " ".join(" ".join(part.split()) for part in parts).lower()


def _safe_local_control_name(raw: Any) -> bool:
    text = str(raw or "").strip()
    return bool(text) and "/" not in text and "\\" not in text and "\x00" not in text and len(text) <= 120


def _safe_sheet_control_name(raw: Any) -> bool:
    text = str(raw or "").strip()
    return _safe_local_control_name(text) and not any(ch in text for ch in "[]:*?/\\")


def _file_create_variant(state: Mapping[str, Any], args: Mapping[str, Any]) -> str:
    explicit = str(args.get("kind") or args.get("type") or args.get("artifact_kind") or args.get("create_type") or "").strip().lower()
    if explicit in {"folder", "directory"}:
        return "folder"
    if explicit in {"project", "workspace"}:
        return "project"
    text = " ".join(
        str(value or "")
        for value in (
            state.get("goal"),
            state.get("last_user_instruction"),
            state.get("user_text"),
            args.get("path"),
            args.get("name"),
            args.get("title"),
        )
    ).lower()
    if re.search(r"\b(?:project|workspace)\b", text) and re.search(r"\b(?:create|make|start|new)\b", text):
        return "project"
    if re.search(r"\b(?:folder|directory)\b", text) and re.search(r"\b(?:create|make|new)\b", text):
        return "folder"
    return ""


def _simple_relative_name(path: Path) -> bool:
    text = str(path)
    return bool(text) and not path.is_absolute() and "/" not in text and "\\" not in text and text not in {".", ".."}


def _versioned_directory(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 100):
        candidate = path.with_name(f"{path.name}-v{index}")
        if not candidate.exists():
            return candidate
    return path.with_name(f"{path.name}-v100")


def _control_tokens_match_owner(raw: str, owner_text: str) -> bool:
    tokens = [token for token in re.findall(r"[a-z0-9]+", str(raw).lower()) if token not in {"v1", "v2"}]
    if not tokens:
        return False
    owner_tokens = set(re.findall(r"[a-z0-9]+", owner_text))
    meaningful = [token for token in tokens if len(token) > 2 or token.startswith("c0")]
    return bool(meaningful) and all(token in owner_tokens for token in meaningful)


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return bool(text) and text not in {"0", "false", "no", "none", "null"}


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


def _at_synthesis_reserve(state: HarnessState) -> bool:
    """True when the loop is about to spend its FINAL budgeted step."""
    if not state.get("agentic_loop") or state.get("goal_satisfied"):
        return False
    budget = int(state.get("max_steps") or MAX_STEPS)
    return int(state.get("current_step") or 0) >= budget - 1


def _agentic_budget_exhausted(state: HarnessState) -> bool:
    if not state.get("agentic_loop") or state.get("goal_satisfied"):
        return False
    budget = int(state.get("max_steps") or MAX_STEPS)
    return int(state.get("current_step") or 0) >= budget


def _planned_action_shape(state: HarnessState) -> str:
    action = dict(state.get("planned_action") or {})
    if action.get("tool"):
        tool_name = str(action.get("tool") or "").replace("_", ".", 1) if "." not in str(action.get("tool") or "") else str(action.get("tool"))
        return action_shape(tool_name, dict(action.get("args") or {}))
    return action_shape(str(state.get("workflow_type") or "general"), {})


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
