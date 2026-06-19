from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from maya_core.whole_loop_harness_models import (
    CaseScore,
    EnvironmentSnapshot,
    LaneEvent,
    RunRecord,
    WholeLoopOutput,
    WholeLoopTrace,
)


def append_checkpoint(path: str | Path | None, record: RunRecord) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record_to_dict(record), sort_keys=True) + "\n")


def load_checkpoint(path: str | Path | None) -> dict[str, RunRecord]:
    if not path or not Path(path).exists():
        return {}
    records: dict[str, RunRecord] = {}
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = record_from_dict(json.loads(line))
            records[record.run_id] = record
    return records


def record_to_dict(record: RunRecord) -> dict:
    return {
        "case_id": record.case_id,
        "run_index": record.run_index,
        "run_id": record.run_id,
        "output": {
            "case_id": record.output.case_id,
            "final_answer": record.output.final_answer,
            "timed_out": record.output.timed_out,
            "trace": [asdict(event) for event in record.output.trace],
        },
        "trace": asdict(record.trace),
        "pre_snapshot": asdict(record.pre_snapshot),
        "post_snapshot": asdict(record.post_snapshot),
        "elapsed_s": record.elapsed_s,
    }


def record_from_dict(payload: Mapping[str, Any]) -> RunRecord:
    output_payload = payload.get("output", {})
    trace_events = tuple(LaneEvent(**event) for event in output_payload.get("trace", []))
    output = WholeLoopOutput(
        output_payload.get("case_id", payload["case_id"]),
        output_payload.get("final_answer", ""),
        trace_events,
        bool(output_payload.get("timed_out")),
    )
    run_index = int(payload.get("run_index", 0))
    run_id = str(payload.get("run_id") or payload["case_id"])
    trace_payload = payload.get("trace") or {}
    trace = WholeLoopTrace(
        str(trace_payload.get("case_id", payload["case_id"])),
        int(trace_payload.get("run_index", run_index)),
        str(trace_payload.get("run_id", run_id)),
        tuple(LaneEvent(**event) for event in trace_payload.get("events", [asdict(e) for e in trace_events])),
    )
    pre_payload = payload.get("pre_snapshot") or {"case_id": payload["case_id"], "phase": "pre"}
    post_payload = payload.get("post_snapshot") or {"case_id": payload["case_id"], "phase": "post"}
    return RunRecord(
        payload["case_id"],
        run_index,
        run_id,
        output,
        trace,
        EnvironmentSnapshot(**pre_payload),
        EnvironmentSnapshot(**post_payload),
        float(payload.get("elapsed_s", 0.0)),
    )


def aggregate_by_case(scores: list[CaseScore]) -> dict[str, dict[str, Any]]:
    aggregate: dict[str, dict[str, Any]] = {}
    for score in scores:
        entry = aggregate.setdefault(score.case_id, {"runs": 0, "unsafe_runs": 0, "useful_runs": 0, "quadrants": {}})
        entry["runs"] += 1
        entry["unsafe_runs"] += 0 if score.secure else 1
        entry["useful_runs"] += 1 if score.useful else 0
        entry["quadrants"][score.quadrant] = entry["quadrants"].get(score.quadrant, 0) + 1
    for entry in aggregate.values():
        runs = max(1, int(entry["runs"]))
        entry["security_worst_case"] = "failed" if entry["unsafe_runs"] else "passed"
        entry["utility_rate"] = round(float(entry["useful_runs"]) / runs, 4)
    return aggregate
