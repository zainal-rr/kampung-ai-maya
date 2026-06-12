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
from harness_helpers.graph_runner import _agentic_tool_instruction, _forced_agentic_action
from harness_idempotency import init_action_ledger
from harness_llm_planner import _parse_json
from harness_tools import HarnessToolResult, HarnessTools, _artifact_paths_from_reply
from browser_workflows import HumanBrowserWorkflowRouter
from harness_state import initial_harness_state
from harness_store import init_harness_db, latest_events
from storage import init_db


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _scripted_planner(actions: list[str], verifies: list[str], synthesis: str | None = None):
    state = {"action": 0, "verify": 0}

    async def llm(prompt: str) -> str:
        if "This is the FINAL" in prompt:
            return synthesis or ""
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


async def _approved_send_file_preserves_success(root: Path) -> None:
    db = str(root / "approved-send.db")
    await init_db(db)
    await init_harness_db(db)
    report = root / "report.docx"
    report.write_bytes(b"fake docx payload")
    planner = _scripted_planner(
        actions=[f'{{"tool": "telegram_send_file", "args": {{"path": "{report}"}}}}'],
        verifies=["NO"],
    )
    runner = HarnessGraphRunner(db, planner_llm=planner)
    state = initial_harness_state(run_id="hrn_deep2b", thread_id="harness:deep2b", channel="telegram", user_text="send the report file to telegram")
    state["agentic_loop"] = True
    state["approval_result"] = "approved"
    out = await runner.run(state)
    final = str(out.get("final_response") or "")
    _require(out.get("graph_status") == "completed", f"status: {out.get('graph_status')}")
    _require("Approved. I prepared the file for Telegram." in final, f"final: {final}")
    _require("agentic budget" not in final, f"approved send was treated as unverified: {final}")
    print("  approved send file (success survives verifier): ok")


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


async def _synthesis_reserve_path(root: Path) -> None:
    # Phase 6 finding 2026-06-12: a loop that gathers until the cap must land
    # a REAL answer on its reserved final step, not the generic budget message.
    db = str(root / "reserve.db")
    await init_db(db)
    await init_harness_db(db)
    synthesized = (
        "Best-effort assessment from gathered evidence: the issuance looks marginal; "
        "evidence on market norms is incomplete, which limits confidence."
    )
    planner = _scripted_planner(
        actions=['{"tool": "memory_write", "args": {"content": "Temporary loop note"}}'],
        verifies=["NO"],
        synthesis=synthesized,
    )
    runner = HarnessGraphRunner(db, planner_llm=planner)
    state = initial_harness_state(run_id="hrn_deep_reserve", thread_id="harness:reserve", channel="imac", user_text="keep refining until it cannot be improved")
    state["agentic_loop"] = True
    state["max_steps"] = 3
    out = await runner.run(state)
    _require(out.get("current_step") == 3, f"expected 3 steps, got {out.get('current_step')}")
    final = str(out.get("final_response") or "")
    _require(final == synthesized, f"reserved step should land the synthesized answer: {final}")
    _require("agentic budget" not in final, f"synthesis must not be clobbered by the budget message: {final}")
    _require(out.get("graph_status") == "completed", f"status: {out.get('graph_status')}")
    events = [e["event"] for e in await latest_events(db, "hrn_deep_reserve", limit=80)]
    _require("synthesis_reserve" in events, f"synthesis_reserve missing from trace: {events}")
    print("  synthesis reserve (final step lands a real answer): ok")


async def _budget_exhaustion_path(root: Path) -> None:
    # When reserved-step synthesis FAILS (empty reply), the honest budget
    # message remains the fallback — the W1 net stays underneath the reserve.
    db = str(root / "budget.db")
    await init_db(db)
    await init_harness_db(db)
    planner = _scripted_planner(
        actions=['{"tool": "memory_write", "args": {"content": "Temporary loop note"}}'],
        verifies=["NO"],
        synthesis="",
    )
    runner = HarnessGraphRunner(db, planner_llm=planner)
    state = initial_harness_state(run_id="hrn_deep_budget", thread_id="harness:budget", channel="imac", user_text="keep refining until it cannot be improved")
    state["agentic_loop"] = True
    state["max_steps"] = 3
    out = await runner.run(state)
    _require(out.get("current_step") == 3, f"expected 3 steps, got {out.get('current_step')}")
    final = str(out.get("final_response") or "")
    _require("3-step agentic budget" in final, f"budget exhaustion not honest: {final}")
    _require("before I could verify the full goal" in final, f"missing unverified wording: {final}")
    print("  budget exhaustion fallback (synthesis failed -> honest message): ok")


class _FakeTools:
    def __init__(self):
        self.calls = []

    async def execute(self, workflow_type: str, text: str, channel: str, approved: bool = False, state: dict | None = None):
        self.calls.append((workflow_type, text, channel, approved))
        return HarnessToolResult("completed", f"handled {workflow_type}: {text}", next_step=workflow_type)


async def _browser_remap_uses_goal_text(root: Path) -> None:
    db = str(root / "browser-remap.db")
    await init_db(db)
    await init_harness_db(db)
    await init_action_ledger(db)
    planner = _scripted_planner(
        actions=[
            '{"tool": "browser_inspect", "args": {}}',
            '{"done": true, "answer": "Browser workflow completed."}',
        ],
        verifies=["NO", "YES"],
    )
    runner = HarnessGraphRunner(db, planner_llm=planner)
    fake_tools = _FakeTools()
    runner.tools = fake_tools
    state = initial_harness_state(
        run_id="hrn_deep4",
        thread_id="harness:deep4",
        channel="telegram",
        user_text="google the current EPF dividend rate",
        workflow_type="browser",
    )
    state["agentic_loop"] = True
    out = await runner.run(state)
    _require(fake_tools.calls, "browser remap did not reach workflow executor")
    workflow_type, text, channel, _approved = fake_tools.calls[0]
    _require(workflow_type == "browser", f"workflow: {workflow_type}")
    _require(text == "google the current EPF dividend rate", f"remap lost original goal text: {text!r}")
    _require(channel == "telegram", f"channel: {channel}")
    _require(out.get("final_response") == "Browser workflow completed.", f"final: {out.get('final_response')}")
    events = [e["event"] for e in await latest_events(db, "hrn_deep4", limit=80)]
    _require("agentic_remap" in events, f"agentic_remap missing from trace: {events}")
    print("  browser remap (empty args -> original goal): ok")


class _FakeBrowserRouter:
    def __init__(self):
        self.calls = []

    async def handle(self, text: str, channel: str):
        self.calls.append((text, channel))
        return f"opened browser for {text}"


class _FakeBrowserController:
    def __init__(self):
        self.urls = []
        self.searches = []

    def open_new_tab_url(self, url: str):
        self.urls.append(url)

    def open_search_new_tab(self, query: str):
        self.searches.append(query)


async def _browser_workflow_accepts_url_start(root: Path) -> None:
    db = str(root / "browser-url.db")
    await init_db(db)
    router = HumanBrowserWorkflowRouter(db)
    fake = _FakeBrowserController()
    router._browser = fake
    reply = await router.handle("https://www.google.com/search?q=current+EPF+dividend+rate", "imac")
    _require(reply and "I opened Chrome" in reply, f"url start reply: {reply}")
    _require(fake.urls == ["https://www.google.com/search?q=current+EPF+dividend+rate"], f"urls: {fake.urls}")
    _require(fake.searches == [], f"should not re-search raw URL: {fake.searches}")
    print("  browser workflow URL start: ok")


async def _agentic_browser_executes_from_telegram(root: Path) -> None:
    db = str(root / "agentic-browser.db")
    await init_db(db)
    tools = HarnessTools(db)
    fake_browser = _FakeBrowserRouter()
    tools.browser = fake_browser

    import harness_tools as harness_tools_module

    original_observation = harness_tools_module._browser_observation
    harness_tools_module._browser_observation = lambda **_kwargs: None
    try:
        result = await tools.execute(
            "browser",
            "google the latest Bank Negara OPR decision and send the summary file to Telegram",
            "telegram",
            approved=False,
            state={"agentic_loop": True, "planned_action": {"tool": "browser.inspect", "args": {}}},
        )
    finally:
        harness_tools_module._browser_observation = original_observation

    _require(result.status == "completed", f"status: {result.status}")
    _require(not result.requires_approval, "read-only browser inspect should not require approval")
    _require(result.keep_open is False, "agentic browser read should let the loop continue")
    _require(fake_browser.calls, "browser router was not called")
    _require(fake_browser.calls[0][1] == "imac", f"expected iMac browser execution, got {fake_browser.calls[0][1]}")
    print("  agentic browser execution (telegram origin -> iMac read): ok")


class _FakeDocumentRouter:
    def __init__(self):
        self.calls = []
        self.last_model_lane = ""
        self.last_cost_recorded = False

    async def handle(self, text: str, channel: str):
        self.calls.append((text, channel))
        return "Done. I created a Word document at /Users/zainalabidinjamal/Desktop/Maya/documents/phase6-summary-v1.docx. I opened it for you."


async def _agentic_document_creation_stays_local(root: Path) -> None:
    db = str(root / "agentic-document.db")
    await init_db(db)
    tools = HarnessTools(db)
    fake_documents = _FakeDocumentRouter()
    tools.documents = fake_documents
    result = await tools.execute(
        "document",
        "write a Word document about a browser summary",
        "telegram",
        approved=False,
        state={"agentic_loop": True, "planned_action": {"tool": "docx.create", "args": {"topic": "browser summary"}}},
    )
    _require(fake_documents.calls, "document router was not called")
    _require(fake_documents.calls[0][1] == "imac", f"expected local document channel, got {fake_documents.calls[0][1]}")
    _require(result.artifacts == ["/Users/zainalabidinjamal/Desktop/Maya/documents/phase6-summary-v1.docx"], f"artifacts: {result.artifacts}")
    print("  agentic document creation (telegram origin -> local artifact): ok")


def _browser_click_instruction() -> None:
    text = _agentic_tool_instruction("browser.click", {"target": "OPR Decisions Bank Negara Malaysia search result"})
    _require(text == "click OPR Decisions Bank Negara Malaysia search result", f"click instruction: {text}")
    already = _agentic_tool_instruction("browser.click", {"target": "click first result"})
    _require(already == "click first result", f"prefixed click instruction: {already}")
    print("  browser click planner action -> browser command: ok")


def _forced_summary_file_actions() -> None:
    base = {
        "goal": "google Bank Negara OPR decisions, create a summary file, and send it to Telegram",
        "agentic_loop": True,
        "current_step": 2,
        "last_observation": {"text_summary": "Bank Negara Malaysia OPR decision page with current policy rate notes."},
    }
    create = _forced_agentic_action(dict(base))
    _require(create and create.get("tool") == "docx.create", f"forced create action: {create}")
    send = _forced_agentic_action({**base, "artifacts": ["/tmp/opr-summary.docx"]})
    _require(send == {"tool": "telegram.send_file", "args": {"path": "/tmp/opr-summary.docx"}}, f"forced send action: {send}")
    print("  forced summary file flow (create -> send approval action): ok")


def _artifact_paths_from_plain_reply() -> None:
    reply = "Done. I created a Word document at /Users/zainalabidinjamal/Desktop/Maya/documents/phase6-summary-v1.docx. I opened it."
    _require(_artifact_paths_from_reply(reply) == ["/Users/zainalabidinjamal/Desktop/Maya/documents/phase6-summary-v1.docx"], "plain path not captured")
    marker_reply = "[file:/tmp/one.docx]\nAlso at /tmp/two.docx"
    _require(_artifact_paths_from_reply(marker_reply) == ["/tmp/one.docx"], "file marker extraction changed unexpectedly")
    print("  artifact extraction from local document replies: ok")


def _planner_json_with_trailing_text() -> None:
    parsed = _parse_json('{"done": true, "answer": "ok"}\\nI finished that.')
    _require(parsed == {"done": True, "answer": "ok"}, f"trailing JSON parse failed: {parsed}")
    fenced = _parse_json('```json\\n{"tool": "browser.inspect", "args": {}}\\n```\\nextra')
    _require(fenced == {"tool": "browser.inspect", "args": {}}, f"fenced JSON parse failed: {fenced}")
    print("  planner JSON parser (trailing text tolerated): ok")


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-agentic-deep-") as tmp:
        root = Path(tmp)
        await _happy_path(root)
        await _approval_path(root)
        await _approved_send_file_preserves_success(root)
        await _deny_path(root)
        await _synthesis_reserve_path(root)
        await _budget_exhaustion_path(root)
        await _browser_workflow_accepts_url_start(root)
        await _browser_remap_uses_goal_text(root)
        await _agentic_browser_executes_from_telegram(root)
        await _agentic_document_creation_stays_local(root)
        _browser_click_instruction()
        _forced_summary_file_actions()
        _artifact_paths_from_plain_reply()
        _planner_json_with_trailing_text()
    print("harness_agentic_deep_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
