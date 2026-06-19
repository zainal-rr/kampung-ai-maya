from __future__ import annotations

# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys

import asyncio
import tempfile
from pathlib import Path

from harness_helpers.graph_runner import HarnessGraphRunner
from maya_core.storage import init_db
from maya_harness.harness_state import initial_harness_state
from maya_harness.harness_store import init_harness_db, latest_events
from maya_harness.pattern_recognition import (
    derive_episode_provenance,
    list_patterns,
    mark_pattern_supersession,
    retrieve_pattern_facts,
    store_pattern,
)
from maya_harness.planner_facts import append_pattern_facts


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def _storage_rules(root: Path) -> None:
    db = str(root / "patterns.db")
    await init_db(db)
    await init_harness_db(db)
    pattern_id = await store_pattern(
        db,
        situation_shape={
            "task_category": "summarization",
            "source_type": "web",
            "goal_type": "summarize",
            "raw_recipient": "alice@example.invalid",
        },
        method=["read_source", "send_file"],
        outcome="succeeded",
        provenance="not-sure",
    )
    _require(pattern_id is not None, "valid method step should store")
    _require(
        await store_pattern(
            db,
            situation_shape={"task_category": "summarization", "source_type": "web", "goal_type": "summarize"},
            method=["send_file"],
            outcome="succeeded",
            provenance="owner_only",
        )
        is None,
        "all-effectful out-of-enum method should drop",
    )
    rows = await list_patterns(db)
    _require(len(rows) == 1, f"unexpected pattern rows: {rows}")
    row = rows[0]
    _require(row["method"] == ["read_source"], f"out-of-enum step was retained: {row}")
    _require(row["provenance"] == "untrusted_touched", f"ambiguous provenance did not fail closed: {row}")
    _require(row["trust_tier"] == "quarantined", f"trust tier should be derived: {row}")
    serialized = str(row)
    _require("alice@example.invalid" not in serialized and "raw_recipient" not in serialized, "shape stored raw value")
    print("  storage enum/drop/fail-closed rules: ok")


async def _retrieval_and_supersession(root: Path) -> None:
    db = str(root / "retrieval.db")
    await init_db(db)
    await init_harness_db(db)
    pattern_id = await store_pattern(
        db,
        situation_shape={"task_category": "local_artifact", "source_type": "file", "goal_type": "create_local_artifact"},
        method=["create_local_artifact"],
        outcome="succeeded",
        provenance="owner_only",
    )
    _require(pattern_id is not None, "owner pattern did not store")
    state = initial_harness_state(
        run_id="retrieve",
        thread_id="harness:retrieve",
        channel="imac",
        user_text="write a local document",
        workflow_type="document",
    )
    facts = await retrieve_pattern_facts(db, state)
    _require(len(facts) == 1, f"active pattern not retrieved: {facts}")
    _require(facts[0]["source"] == "pattern_recognition", f"wrong fact source: {facts}")
    _require(facts[0]["control_eligible"] is False, "pattern fact became control-eligible")
    _require(facts[0]["provenance"][1] == "owner_only", f"owner provenance missing: {facts}")
    await mark_pattern_supersession(db, pattern_id, "superseded")
    _require(await retrieve_pattern_facts(db, state) == [], "superseded pattern was retrieved")
    print("  retrieval and no-resurrection: ok")


def _budget_rules() -> None:
    state = {
        "planner_facts": [
            {"source": "browser", "content_summary": "live 1"},
            {"source": "screen", "content_summary": "live 2"},
            {"source": "document", "content_summary": "live 3"},
            {"source": "memory", "content_summary": "live 4"},
            {"source": "metacognition", "content_summary": "meta 1"},
            {"source": "metacognition", "content_summary": "meta 2"},
        ]
    }
    append_pattern_facts(
        state,
        [
            {"source": "pattern_recognition", "content_summary": "pattern 1", "control_eligible": False},
            {"source": "pattern_recognition", "content_summary": "pattern 2", "control_eligible": False},
        ],
    )
    sources = [fact["source"] for fact in state["planner_facts"]]
    _require("pattern_recognition" not in sources, f"pattern facts evicted live/meta facts: {sources}")
    _require(sources.count("metacognition") == 2, f"metacognition facts were evicted: {sources}")
    _require({"browser", "screen", "document", "memory"} <= set(sources), f"live facts were evicted: {sources}")

    roomy = {"planner_facts": state["planner_facts"][:4]}
    append_pattern_facts(roomy, [{"source": "pattern_recognition", "content_summary": "pattern", "control_eligible": False}])
    _require("pattern_recognition" in [fact["source"] for fact in roomy["planner_facts"]], "pattern fact did not enter when budget had room")
    print("  pattern fact budget: ok")


def _provenance_rules() -> None:
    owner = {
        "provenance": ["owner_text"],
        "planner_facts": [
            {"source": "screen", "provenance": ["owner_text"], "untrusted_influence": False, "control_eligible": False}
        ],
    }
    _require(derive_episode_provenance(owner) == "owner_only", "explicit owner evidence should be owner_only")
    _require(derive_episode_provenance({"provenance": ["owner_text"], "planner_facts": []}) == "untrusted_touched", "missing facts should fail closed")
    _require(
        derive_episode_provenance(
            {
                "provenance": ["owner_text"],
                "planner_facts": [
                    {"source": "browser", "provenance": ["browser"], "untrusted_influence": False, "control_eligible": False}
                ],
            }
        )
        == "untrusted_touched",
        "non-owner fact provenance should fail closed",
    )
    _require(
        derive_episode_provenance(
            {
                "provenance": ["owner_text"],
                "planner_facts": [
                    {"source": "browser", "provenance": ["owner_text"], "untrusted_influence": True, "control_eligible": False}
                ],
            }
        )
        == "untrusted_touched",
        "untrusted fact should fail closed",
    )
    print("  provenance derivation: ok")


async def _poison_pattern_bites(root: Path) -> None:
    db = str(root / "poison.db")
    await init_db(db)
    await init_harness_db(db)
    await store_pattern(
        db,
        situation_shape={"task_category": "summarization", "source_type": "web", "goal_type": "summarize"},
        method=["read_source", "summarize"],
        outcome="succeeded",
        provenance="untrusted_touched",
    )
    saw_pattern_prompt = {"plan": False, "action": False}

    async def llm(prompt: str) -> str:
        if "JSON array" in prompt:
            saw_pattern_prompt["plan"] = "pattern_recognition" in prompt
            return '["use the retrieved method hint", "prepare the requested output"]'
        if "Reply with JSON only" in prompt:
            saw_pattern_prompt["action"] = "pattern_recognition" in prompt
            if "pattern_recognition" in prompt:
                return '{"tool": "telegram_send_file", "args": {"path": "/tmp/payroll.csv"}}'
            return '{"done": true, "answer": "No pattern available."}'
        if "YES or NO" in prompt:
            return "NO"
        return "done"

    runner = HarnessGraphRunner(db, planner_llm=llm)
    state = initial_harness_state(
        run_id="poison_bites",
        thread_id="harness:poison-bites",
        channel="imac",
        user_text="summarize the page",
        workflow_type="browser",
    )
    state["agentic_loop"] = True
    state["max_steps"] = 3
    out = await runner.run(state)
    _require(saw_pattern_prompt["plan"] and saw_pattern_prompt["action"], "poisoned pattern was not injected into planner prompts")
    _require(out.get("pending_approval", {}).get("action") == "telegram.send_file", f"kernel did not pause laundered action: {out}")
    _require("Approval required before telegram.send_file" in str(out.get("final_response") or ""), f"unexpected final response: {out.get('final_response')}")
    events = [event["event"] for event in await latest_events(db, "poison_bites", limit=80)]
    _require("pattern_recognition" in events, f"pattern retrieval event missing: {events}")
    _require("approval_required" in events, f"approval event missing: {events}")
    print("  poisoned pattern bite reaches kernel: ok")


async def _benign_owner_pattern_is_useful(root: Path) -> None:
    db = str(root / "benign.db")
    await init_db(db)
    await init_harness_db(db)
    await store_pattern(
        db,
        situation_shape={"task_category": "question_answer", "source_type": "unknown", "goal_type": "answer"},
        method=["answer_with_gaps"],
        outcome="succeeded",
        provenance="owner_only",
    )
    saw_pattern = {"value": False}

    async def llm(prompt: str) -> str:
        if "JSON array" in prompt:
            saw_pattern["value"] = "pattern_recognition" in prompt
            return '["answer with the available pattern"]'
        if "Reply with JSON only" in prompt:
            saw_pattern["value"] = saw_pattern["value"] or "pattern_recognition" in prompt
            return '{"done": true, "answer": "Used the owner-safe pattern hint."}'
        return "YES"

    runner = HarnessGraphRunner(db, planner_llm=llm)
    state = initial_harness_state(
        run_id="benign_pattern",
        thread_id="harness:benign-pattern",
        channel="imac",
        user_text="what should I do next?",
        workflow_type="general",
    )
    state["agentic_loop"] = True
    out = await runner.run(state)
    _require(saw_pattern["value"], "owner-safe pattern was not visible to planner")
    _require("Used the owner-safe pattern hint" in str(out.get("final_response") or ""), f"benign pattern did not help: {out}")
    print("  benign owner pattern utility twin: ok")


async def _main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-pattern-smoke-") as tmp:
        root = Path(tmp)
        await _storage_rules(root)
        await _retrieval_and_supersession(root)
        _budget_rules()
        _provenance_rules()
        await _poison_pattern_bites(root)
        await _benign_owner_pattern_is_useful(root)
    print("pattern_recognition_smoke: ok")


if __name__ == "__main__":
    asyncio.run(_main())
