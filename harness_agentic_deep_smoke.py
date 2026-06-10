"""Deterministic smoke for the deepened agentic loop.

Proves, without any live model:
1. The executor consumes the planner's tool choice (memory.write runs inline).
2. The loop continues to a second pass and finishes on the planner's done.
3. Approval-required tools pause the run through the existing gate.
4. Permission-denied tool args produce an honest refusal, not an action.
5. Trace events record agentic_action / loop_iteration / planner_done.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from harness_graph import HarnessGraphRunner
from harness_state import initial_harness_state
from harness_store import init_harness_db, latest_events
from storage import init_db


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _scripted_planner(actions: list[str], verifies: list[str]):
    state = {"action": 0, "verify": 0}

    async def llm(prompt: str) -> str:
        if "YES or NO" in prompt:
            reply = verifies[min(state["verify"], len(verifies) - 1)]
            state["verify"] += 1
            return reply
        if "Reply with JSON only" in prompt:
            reply = actions[min(state["action"], len(actions) - 1)]
            state["action"] += 1
            return reply
        return '["gather facts", "record them"]'

    return llm


async def _happy_path(root: Path) -> None:
    db = str(root / "happy.db")
    await init_db(db)
    await init_harness_db(db)
    planner = _scripted_planner(
        actions=[
            '{"tool": "memory_write", "args": {"content": "Customer A circuit uses VRF CUST-A", "kind": "lesson"}}',
            '{"done": true, "answer": "Recorded the customer fact and finished."}',
        ],
        verifies=["NO", "YES"],
    )
    runner = HarnessGraphRunner(db, planner_llm=planner)
    state = initial_harness_state(run_id="hrn_deep1", thread_id="harness:deep1", channel="imac", user_text="remember the customer circuit details")
    state["agentic_loop"] = True
    out = await runner.run(state)
    _require(out.get("current_step") == 2, f"expected 2 loop passes, got {out.get('current_step')}")
    _require(out.get("final_response") == "Recorded the customer fact and finished.", f"final: {out.get('final_response')}")
    _require(out.get("graph_status") == "completed", f"status: {out.get('graph_status')}")
    events = [e["event"] for e in await latest_events(db, "hrn_deep1", limit=80)]
    for marker in ("agentic_action", "loop_iteration"):
        _require(marker in events, f"missing {marker} in trace: {events}")
    details = " ".join(str(e["details"]) for e in await latest_events(db, "hrn_deep1", limit=80))
    _require("agentic memory.write" in details, "memory.write execution not recorded")
    from canonical_memory import search_relevant_canonical_memories

    memories = await search_relevant_canonical_memories(db, "customer circuit VRF")
    _require(any("CUST-A" in m for m in memories), f"memory not written: {memories}")
    print("  happy path (tool -> loop -> done): ok")


async def _approval_path(root: Path) -> None:
    db = str(root / "approval.db")
    await init_db(db)
    await init_harness_db(db)
    planner = _scripted_planner(
        actions=['{"tool": "telegram_send_file", "args": {"path": "/tmp/report.docx"}}'],
        verifies=["YES"],
    )
    runner = HarnessGraphRunner(db, planner_llm=planner)
    state = initial_harness_state(run_id="hrn_deep2", thread_id="harness:deep2", channel="imac", user_text="send the report file to telegram")
    state["agentic_loop"] = True
    out = await runner.run(state)
    _require(bool(out.get("pending_approval")), "approval-required tool should pause the run")
    _require("telegram.send_file" in str(out.get("pending_approval")), f"pending: {out.get('pending_approval')}")
    _require(out.get("graph_status") == "waiting_approval", f"status: {out.get('graph_status')}")
    print("  approval gate (sensitive tool pauses): ok")


async def _deny_path(root: Path) -> None:
    db = str(root / "deny.db")
    await init_db(db)
    await init_harness_db(db)
    planner = _scripted_planner(
        actions=['{"tool": "file_create", "args": {"path": "note.txt", "content": "my password is hunter2"}}'],
        verifies=["YES"],
    )
    runner = HarnessGraphRunner(db, planner_llm=planner)
    state = initial_harness_state(run_id="hrn_deep3", thread_id="harness:deep3", channel="imac", user_text="save my password somewhere")
    state["agentic_loop"] = True
    out = await runner.run(state)
    _require("sensitive private information" in str(out.get("final_response", "")).lower(), f"deny reason missing: {out.get('final_response')}")
    events = [e["event"] for e in await latest_events(db, "hrn_deep3", limit=40)]
    _require("tool_denied" in events, f"tool_denied missing from trace: {events}")
    print("  permission deny (honest refusal, no action): ok")


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-agentic-deep-") as tmp:
        root = Path(tmp)
        await _happy_path(root)
        await _approval_path(root)
        await _deny_path(root)
    print("harness_agentic_deep_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
