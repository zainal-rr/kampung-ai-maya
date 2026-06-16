from __future__ import annotations

"""Live agentic reliability harness for the /complex + harness lane.

Runs scripted multi-turn scenarios through HarnessRouter — the same entry
point Telegram and the iMac use — with a FRESH router per turn so every
scenario also proves sqlite checkpoint persistence across process restarts.
Records scenario evidence (turns, runs, events, artifacts on disk, approvals)
and labels each scenario pass/partial/fail.

Usage:
  ./venv/bin/python live_agentic_reliability_run.py --dry-run
  ./venv/bin/python live_agentic_reliability_run.py --night-id agentic1
Re-running with the same --night-id resumes and skips completed scenarios.
"""

import argparse
import asyncio
from datetime import datetime
from pathlib import Path

from agentic_lane_validators import validate_scenario
from agentic_reliability_scenarios import AgenticScenario, agentic_scenarios
from agentic_run_evidence import (
    AGENTIC_RELIABILITY_DIR,
    add_turn,
    agentic_night_summary,
    append_scenario,
    collect_scenario_state,
    existing_run_ids,
    load_scenarios,
    new_scenario_record,
    scenario_to_dict,
    write_agentic_markdown,
)


CHANNEL = "imac"


async def run_agentic_night(
    night_id: str,
    *,
    dry_run: bool,
    only: str = "all",
    base_dir: Path | None = None,
    settle_seconds: float = 1.0,
) -> dict:
    night_dir = (base_dir or AGENTIC_RELIABILITY_DIR) / night_id
    jsonl = night_dir / "scenarios.jsonl"
    done = {row["scenario_id"] for row in load_scenarios(jsonl)}
    scenarios = agentic_scenarios(only)
    db_path = str(night_dir / "night.db")
    if not dry_run:
        night_dir.mkdir(parents=True, exist_ok=True)
        from harness_store import init_harness_db
        from storage import init_db

        await init_db(db_path)
        await init_harness_db(db_path)
    for scenario in scenarios:
        if scenario.id in done:
            print(f"skip (done): {scenario.id}")
            continue
        if dry_run or (scenario.live_only and dry_run):
            record = _dry_run_scenario(scenario, night_id)
        else:
            record = await _run_scenario(scenario, night_id, db_path)
            await _cleanup_leftover_runs(db_path)
            if settle_seconds > 0:
                await asyncio.sleep(settle_seconds)
        append_scenario(record, jsonl)
        print(f"{record.status.upper():7s} {scenario.id}" + (f" | {record.reasons[0]}" if record.reasons else ""))
    rows = load_scenarios(jsonl)
    write_agentic_markdown(rows, night_dir / "night.md")
    summary = agentic_night_summary(rows)
    _print_summary(night_id, summary)
    return summary


async def _run_scenario(scenario: AgenticScenario, night_id: str, db_path: str):
    from harness_router import HarnessRouter

    record = new_scenario_record(scenario.id, night_id, scenario.title)
    before = await existing_run_ids(db_path)
    for turn in scenario.turns:
        text = {"approve": "yes", "decline": "no"}.get(turn.kind, turn.text)
        try:
            if turn.kind == "seed_complex":
                reply = await _seed_complex_workflow(db_path, turn.text)
            else:
                router = HarnessRouter(db_path)  # fresh instance: proves checkpoint persistence
                reply = await router.handle(text, CHANNEL)
        except Exception as exc:  # noqa: BLE001 - a crashed turn must still be recorded
            reply = f"(runner exception: {type(exc).__name__}: {exc})"
        add_turn(record, turn.text, turn.kind, reply or "(not handled by harness)")
    await collect_scenario_state(record, db_path, before)
    verdict = validate_scenario(scenario_to_dict(record), scenario, live=True)
    record.status = verdict.status
    record.reasons = list(verdict.reasons)
    return record


def _dry_run_scenario(scenario: AgenticScenario, night_id: str):
    record = new_scenario_record(scenario.id, night_id, scenario.title)
    for turn in scenario.turns:
        add_turn(record, turn.text, turn.kind, "(dry-run: routing and classification only)")
    record.finished_at = record.started_at
    verdict = validate_scenario(scenario_to_dict(record), scenario, live=False)
    record.status = verdict.status
    record.reasons = list(verdict.reasons)
    return record


async def _seed_complex_workflow(db_path: str, request: str) -> str:
    """Create the /complex execution workflow exactly as the complex lane does,
    with a canned plan so the approval-gate machinery is tested without LLMs."""
    from complex_agentic_bridge import create_agentic_workflow_from_complex_plan, format_agentic_workflow_notice

    workflow = await create_agentic_workflow_from_complex_plan(
        db_path,
        source_run_id="agentic-night-seed",
        request=request,
        plan="Summary\n1. Inspect the failing area.\n2. Prepare a bounded repair proposal.\n3. Verify before applying anything.",
        review="PASS: safe while changes stay proposal-only and apply requires approval.",
        graph=[],
        channel=CHANNEL,
    )
    return format_agentic_workflow_notice(workflow)


async def _cleanup_leftover_runs(db_path: str) -> None:
    from harness_store import finish_run, list_active_runs, record_event

    for run in await list_active_runs(db_path, CHANNEL):
        await record_event(db_path, run["run_id"], "runner_cleanup", "scenario finished; runner closed leftover run")
        await finish_run(db_path, run["run_id"], status="cancelled")


def _print_summary(night_id: str, summary: dict) -> None:
    print(f"\nagentic night {night_id} summary:")
    print(f"  completion: {summary['completion_rate']}% ({summary['pass']}/{summary['total']})")
    for key in ("false_saved_criticals", "approval_criticals", "lost_state_criticals", "honesty_criticals"):
        print(f"  {key}: {summary[key]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Live agentic reliability night")
    parser.add_argument("--night-id", default="")
    parser.add_argument("--only", default="all", help="run a single scenario id")
    parser.add_argument("--dry-run", action="store_true", help="routing + classification only")
    parser.add_argument("--settle-seconds", type=float, default=1.0)
    args = parser.parse_args()
    night_id = args.night_id or datetime.now().strftime("%Y%m%d_%H%M%S") + ("_dry" if args.dry_run else "")
    asyncio.run(
        run_agentic_night(night_id, dry_run=args.dry_run, only=args.only, settle_seconds=args.settle_seconds)
    )


if __name__ == "__main__":
    main()
