from __future__ import annotations

from typing import Literal

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

from browser_agent_state import task_type_for
from harness_state import HarnessState
from harness_artifact_store import record_structured_artifact
from harness_checkpoint_migration import snapshot_or_migrate
from harness_execution import execute_with_ledger
from harness_observation_store import record_observation
from harness_store import create_approval, finish_run, record_artifact, record_event, upsert_run
from harness_tools import HarnessTools
from harness_workflows import classify_workflow, next_step_for, plan_for, workflow_for_action


class HarnessGraphRunner:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.tools = HarnessTools(db_path)

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
        graph.add_edge("verify", "memory_update")
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
        if not state.get("plan"):
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
            state["last_observation"] = result.observation.as_dict()
            if state.get("workflow_type") == "browser":
                state["browser_state"] = _browser_state(state, result.observation.as_dict())
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


def _resume_message(state: HarnessState) -> str:
    plan = state.get("plan") or []
    step = int(state.get("current_step") or 0)
    if plan:
        return f"I still have this workflow open: {state.get('goal', '')}. Last step: {plan[min(step, len(plan)-1)]}."
    return f"I still have this workflow open: {state.get('goal', '')}."


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


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
