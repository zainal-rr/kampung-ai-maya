from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys

import asyncio
from dataclasses import replace

from maya_core.c0_capability_baseline import (
    CapabilityOracle,
    CapabilityTask,
    CapabilityTaskResult,
    build_maya_domain_capability_manifest,
    make_report,
    run_capability_baseline,
    scripted_planner_llm,
    write_report,
    _score_outcome,
    _trace_grounded_reason,
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _test_manifest_stable_and_reversible() -> None:
    manifest = build_maya_domain_capability_manifest()
    ids = [task.task_id for task in manifest.tasks]
    _require(manifest.manifest_id == "maya_domain_capability_v1", f"manifest id: {manifest.manifest_id}")
    _require(len(ids) >= 30, f"expected about 30 tasks, got {len(ids)}")
    _require(len(set(ids)) == len(ids), "task ids must be unique")
    _require(bool(manifest.manifest_sha), "manifest sha missing")
    forbidden = ("pay ", "book ", "delete ", "send ")
    unsafe_prompts = [
        task.task_id
        for task in manifest.tasks
        if any(word in task.prompt.lower() for word in forbidden)
        and task.oracle.oracle_type not in {"honest_stop", "approval_required"}
    ]
    _require(not unsafe_prompts, f"irreversible prompts must be negative/honesty only: {unsafe_prompts}")
    print("  manifest stability and reversible scope: ok")


def _test_dummy_manifest_runs_without_provider() -> None:
    async def run() -> None:
        manifest = build_maya_domain_capability_manifest()
        tiny = replace(manifest, tasks=manifest.tasks[-3:])
        results, workspace = await run_capability_baseline(tiny, planner_llm=scripted_planner_llm(), semantic_evaluator=None)
        _require(len(results) == 3, f"result count: {len(results)}")
        _require(workspace, "workspace stamp missing")
        _require(all(result.outcome in {"success", "partial", "fail", "honest_stop"} for result in results), f"bad outcomes: {results}")

    asyncio.run(run())
    print("  dummy manifest runs without provider calls: ok")


def _test_deferred_report_shape() -> None:
    manifest = build_maya_domain_capability_manifest()
    report = make_report(
        status="deferred",
        manifest=manifest,
        started_at="2026-06-20T00:00:00+00:00",
        provider_status="deferred",
        evaluator_status="not_run",
        model_config={"provider": "openai", "model": "gpt-5.5", "temperature": 0.0, "seed": "c0-current"},
        command="python scripts/run_c0_capability_baseline.py",
        deferred_reason="missing OPENAI_API_KEY",
    )
    payload = write_report(report)
    _require(payload["status"] == "deferred", f"status: {payload}")
    _require(payload["deferred_reason"] == "missing OPENAI_API_KEY", f"reason: {payload}")
    _require(payload["manifest_sha"] == manifest.manifest_sha, "manifest sha not stamped")
    print("  provider-missing path reports deferred: ok")


def _test_semantic_oracle_is_not_literal_fragment() -> None:
    async def evaluator(answer: str, task: CapabilityTask, payload: dict) -> dict[str, str]:
        del task, payload
        # This accepts by meaning. The answer intentionally does not contain
        # the literal word "summary", which caught the Step 0.5 scorer bug.
        if "measure" in answer.lower() and "before" in answer.lower() and "building" in answer.lower():
            return {"outcome": "success", "reason": "semantic meaning present without literal fragment"}
        return {"outcome": "fail", "reason": "meaning absent"}

    async def run() -> None:
        task = CapabilityTask(
            "semantic_no_literal",
            "question_answer",
            "Explain C0.",
            CapabilityOracle("semantic_answer", rubric="Should say C0 measures before building."),
        )
        payload = {"state": {"final_response": "C0 measures the current loop before building C1-C6."}, "events": (), "artifacts": ()}
        outcome, status = await _score_outcome(task, payload, evaluator)
        _require(outcome == "success", f"semantic evaluator should pass without literal fragment: {outcome}, {status}")

    asyncio.run(run())
    print("  semantic answer oracle is not literal-fragment matching: ok")


def _test_artifact_honest_stop_is_not_success() -> None:
    async def run() -> None:
        task = CapabilityTask("artifact_stop", "local_artifact", "Create a note.", CapabilityOracle("artifact", expected_artifact=True))
        payload = {"state": {"final_response": "Approval required before file.create."}, "events": (), "artifacts": (), "timed_out": False}
        outcome, status = await _score_outcome(task, payload, None)
        _require(outcome == "partial", f"artifact honest stop should be partial capability miss: {outcome}, {status}")

    asyncio.run(run())
    print("  artifact honest stop is a capability miss, not success: ok")


def _test_unallowed_semantic_honest_stop_becomes_fail() -> None:
    async def evaluator(answer: str, task: CapabilityTask, payload: dict) -> dict[str, str]:
        del answer, task, payload
        return {"outcome": "honest_stop", "reason": "stopped instead of answering"}

    async def run() -> None:
        task = CapabilityTask("semantic_stop", "question_answer", "Answer.", CapabilityOracle("semantic_answer", rubric="Should answer."))
        payload = {"state": {"final_response": "I stopped."}, "events": (), "artifacts": (), "timed_out": False}
        outcome, status = await _score_outcome(task, payload, evaluator)
        _require(outcome == "fail", f"unallowed honest stop should fail semantic task: {outcome}, {status}")

    asyncio.run(run())
    print("  unallowed semantic honest stop is not counted as success: ok")


def _test_ambiguous_reason_becomes_unknown() -> None:
    task = CapabilityTask("ambiguous", "question_answer", "Answer something.", CapabilityOracle("semantic_answer"))
    payload = {
        "state": {"final_response": "I tried but did not finish.", "graph_status": "completed"},
        "events": ({"event": "ingest", "details": "x"}, {"event": "finish", "details": "completed"}),
        "artifacts": (),
        "timed_out": False,
    }
    reason, component = _trace_grounded_reason(task, payload, "fail")
    _require(reason == "unknown" and component == "", f"ambiguous reason must not be guessed: {reason}, {component}")
    print("  ambiguous trace attribution becomes unknown: ok")


def _test_artifact_planner_done_is_trace_grounded_strategy() -> None:
    task = CapabilityTask("artifact_planner_done", "local_artifact", "Create a note.", CapabilityOracle("artifact", expected_artifact=True))
    payload = {
        "state": {"final_response": "Done.", "graph_status": "completed"},
        "events": ({"event": "execute", "details": "planner_done"},),
        "artifacts": (),
        "timed_out": False,
    }
    reason, component = _trace_grounded_reason(task, payload, "fail")
    _require(reason == "planner_strategy" and component == "planner", f"expected planner_strategy: {reason}, {component}")
    print("  artifact miss from planner_done is trace-grounded strategy: ok")


def _test_report_parser_counts_reason_codes() -> None:
    manifest = build_maya_domain_capability_manifest()
    results = (
        CapabilityTaskResult("a", "question_answer", "success", "unknown", "", "semantic_answer", "semantic:ok", "ok", "completed"),
        CapabilityTaskResult("b", "local_artifact", "fail", "tool_gap", "tool", "artifact", "deterministic_artifact_missing", "no", "completed"),
    )
    report = make_report(
        status="complete",
        manifest=manifest,
        started_at="2026-06-20T00:00:00+00:00",
        provider_status="scripted",
        evaluator_status="none",
        model_config={"provider": "scripted", "model": "scripted_c0", "temperature": 0.0, "seed": "c0-current"},
        command="python scripts/run_c0_capability_baseline.py --planner scripted",
        results=results,
    )
    payload = write_report(report)
    _require(payload["counts"]["success"] == 1 and payload["counts"]["fail"] == 1, f"counts: {payload['counts']}")
    _require(payload["reason_counts"]["tool_gap"] == 1, f"reason counts: {payload['reason_counts']}")
    _require(payload["model_config"]["temperature"] == 0.0, "temperature stamp missing")
    print("  report parser validates counts and provenance stamp: ok")


def main() -> None:
    _test_manifest_stable_and_reversible()
    _test_dummy_manifest_runs_without_provider()
    _test_deferred_report_shape()
    _test_semantic_oracle_is_not_literal_fragment()
    _test_artifact_honest_stop_is_not_success()
    _test_unallowed_semantic_honest_stop_becomes_fail()
    _test_ambiguous_reason_becomes_unknown()
    _test_artifact_planner_done_is_trace_grounded_strategy()
    _test_report_parser_counts_reason_codes()
    print("c0_capability_baseline_smoke: ok")


if __name__ == "__main__":
    main()
