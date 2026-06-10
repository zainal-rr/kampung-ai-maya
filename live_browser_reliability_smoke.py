from __future__ import annotations

"""Offline proof that the reliability harness runs a full 70-prompt night.

Runs the complete prompt bank in dry-run mode (routing + parsing, no browser)
into a temporary directory, then asserts the evidence files, lane coverage,
resume behavior, and summary counters. This is the CI gate for the harness
itself; the live night on the iMac uses the same code path with dry_run=False.
"""

import asyncio
import tempfile
from pathlib import Path

from browser_run_evidence import load_runs
from live_browser_reliability_run import run_night


EXPECTED_LANES = {"flights", "stays", "google_search", "google_images", "youtube", "reddit", "safety"}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def _main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-reliability-") as tmp:
        base = Path(tmp)
        summary = await run_night(
            "all", 0, "ci_dry", dry_run=True, screenshots=False, settle_seconds=0, base_dir=base
        )
        night_dir = base / "ci_dry"
        runs = load_runs(night_dir / "runs.jsonl")
        _require(len(runs) == 70, f"expected 70 runs, got {len(runs)}")
        _require({run["lane"] for run in runs} == EXPECTED_LANES, "lane coverage incomplete")
        _require(summary["completion_rate"] == 100.0, f"dry-run completion should be 100%, got {summary['completion_rate']}")
        _require(summary["safety_passed"] == 10 and summary["safety_total"] == 10, "safety stops incomplete")
        for key in ("stale_context_criticals", "hallucination_criticals", "honesty_criticals", "safety_criticals"):
            _require(summary[key] == 0, f"{key} should be 0 in dry run")
        _require((night_dir / "night.md").exists(), "night markdown report missing")
        sample = runs[0]
        for field in ("prompt", "parsed_intent", "route_skill", "steps", "answer", "status", "started_at"):
            _require(field in sample, f"run record missing {field}")
        flights = [run for run in runs if run["lane"] == "flights"]
        _require(all(run["parsed_intent"].get("destination") for run in flights), "flight intent extraction incomplete")
        clarify = [run for run in flights if "Tokyo" in run["prompt"]]
        _require(clarify and "departure date" in clarify[0]["parsed_intent"].get("missing", ""), "missing-date case not flagged")

        # Resume: a second invocation must skip all completed runs and add none.
        await run_night("all", 0, "ci_dry", dry_run=True, screenshots=False, settle_seconds=0, base_dir=base)
        _require(len(load_runs(night_dir / "runs.jsonl")) == 70, "resume duplicated runs")

    print("live_browser_reliability_smoke: ok")


if __name__ == "__main__":
    asyncio.run(_main())
