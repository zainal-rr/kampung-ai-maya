from __future__ import annotations

"""Offline proof of the agentic reliability harness.

1) Dry-runs the full scenario bank (routing + classification).
2) Executes the non-document scenarios live against a temp harness db with a
   faked browser, asserting approval gates, checkpoint resume across fresh
   router instances, clean stops, and evidence files.
3) Unit-checks the critical validators with planted false-saved,
   approval-bypass, and lost-state rows.
"""

import asyncio
import os
import tempfile
from pathlib import Path

import utils
from agentic_lane_validators import validate_scenario
from agentic_reliability_scenarios import agentic_scenarios
from agentic_run_evidence import load_scenarios
from live_agentic_reliability_run import run_agentic_night


LIVE_SUBSET = (
    "flight_followup_stop",
    "self_heal_proposal",
    "complex_gate_decline",
    "complex_gate_approve",
    "kill_and_resume",
    "status_probe",
    "stop_when_idle",
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _fake_applescript(script: str) -> str:
    if "pageTitle" in script:
        return "Flights\n---URL---\nhttps://example.test/flights\n---TEXT---\nAirAsia RM120\nMalaysia Airlines RM180"
    if "rawJson" in script:
        return '[{"kind":"button","label":"Search flights"},{"kind":"input","label":"Departure"}]'
    if "fillResult" in script:
        return "FILLED: field"
    if "visibleResult" in script:
        return "false"
    if "clickResult" in script:
        return "CLICKED: Search flights"
    return ""


async def _main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-agentic-") as tmp:
        base = Path(tmp)
        summary = await run_agentic_night("ci_dry", dry_run=True, base_dir=base, settle_seconds=0)
        rows = load_scenarios(base / "ci_dry" / "scenarios.jsonl")
        _require(len(rows) == len(agentic_scenarios()), "dry run did not cover every scenario")
        _require(summary["completion_rate"] == 100.0, f"dry-run classification should be 100%, got {summary}")

        originals = (
            utils.OSBridge._run_applescript,
            getattr(utils.OSBridge, "open_url", None),
            getattr(utils.OSBridge, "open_url_new_tab", None),
            os.environ.get("MAYA_BROWSER_DRIVER"),
        )
        os.environ["MAYA_BROWSER_DRIVER"] = "legacy"
        utils.OSBridge._run_applescript = lambda self, script: _fake_applescript(script)
        utils.OSBridge.open_url = lambda self, url, app_name="Google Chrome": None
        utils.OSBridge.open_url_new_tab = lambda self, url, app_name="Google Chrome": None
        try:
            for scenario_id in LIVE_SUBSET:
                await run_agentic_night("ci_live", dry_run=False, only=scenario_id, base_dir=base, settle_seconds=0)
        finally:
            utils.OSBridge._run_applescript = originals[0]
            utils.OSBridge.open_url = originals[1]
            utils.OSBridge.open_url_new_tab = originals[2]
            if originals[3] is None:
                os.environ.pop("MAYA_BROWSER_DRIVER", None)
            else:
                os.environ["MAYA_BROWSER_DRIVER"] = originals[3]
        rows = {row["scenario_id"]: row for row in load_scenarios(base / "ci_live" / "scenarios.jsonl")}
        _require(set(rows) == set(LIVE_SUBSET), "live subset incomplete")
        for scenario_id in LIVE_SUBSET:
            row = rows[scenario_id]
            criticals = [reason for reason in row["reasons"] if str(reason).startswith("critical:")]
            _require(not criticals, f"{scenario_id} has criticals: {criticals}")
            _require(row["status"] in ("pass", "partial"), f"{scenario_id} failed: {row['reasons']}")
        _require(rows["complex_gate_decline"]["status"] == "pass", f"decline gate: {rows['complex_gate_decline']['reasons']}")
        _require(rows["kill_and_resume"]["status"] == "pass", f"checkpoint resume: {rows['kill_and_resume']['reasons']}")
        _require(any(a["status"] == "declined" for a in rows["complex_gate_decline"]["approvals"]), "declined approval not recorded")
        _require((base / "ci_live" / "night.md").exists(), "agentic night report missing")

    # Planted critical cases must be caught.
    scenario = next(s for s in agentic_scenarios() if s.id == "excel_budget")
    fake = {
        "turns": [{"text": scenario.turns[0].text, "kind": "turn", "reply": "Done. I created the file and saved it."},
                  {"text": scenario.turns[1].text, "kind": "probe", "reply": "Latest artifacts: 1) document: excel"}],
        "run_ids": ["r1"], "workflow_types": ["document"], "statuses": {"r1": "completed"},
        "events": {"r1": [{"event": "a", "details": ""}, {"event": "b", "details": ""}]},
        "artifacts": [{"run_id": "r1", "kind": "document", "path": "/tmp/missing.xlsx", "exists": False, "size": 0}],
        "approvals": [],
    }
    verdict = validate_scenario(fake, scenario, live=True)
    _require(any(r.startswith("critical:false-saved") for r in verdict.reasons), "false-saved claim not caught")

    decline = next(s for s in agentic_scenarios() if s.id == "complex_gate_decline")
    bypass = {
        "turns": [{"text": decline.turns[0].text, "kind": "turn", "reply": "waiting for approval"},
                  {"text": decline.turns[1].text, "kind": "decline", "reply": "Okay, I won't do that."}],
        "run_ids": ["r2"], "workflow_types": ["self_heal"], "statuses": {"r2": "completed"},
        "events": {"r2": [{"event": "a", "details": ""}, {"event": "b", "details": ""}]},
        "artifacts": [], "approvals": [{"run_id": "r2", "action": "x", "status": "declined"}],
    }
    verdict = validate_scenario(bypass, decline, live=True)
    _require(any(r.startswith("critical:approval") for r in verdict.reasons), "approval bypass not caught")

    resume = next(s for s in agentic_scenarios() if s.id == "kill_and_resume")
    lost = {
        "turns": [{"text": resume.turns[0].text, "kind": "turn", "reply": "started"},
                  {"text": resume.turns[1].text, "kind": "probe", "reply": "No active workflow right now."},
                  {"text": resume.turns[2].text, "kind": "turn", "reply": "Okay. I closed the active workflow."}],
        "run_ids": ["r3"], "workflow_types": ["browser"], "statuses": {"r3": "cancelled"},
        "events": {"r3": [{"event": "a", "details": ""}, {"event": "b", "details": ""}, {"event": "c", "details": ""}]},
        "artifacts": [], "approvals": [],
    }
    verdict = validate_scenario(lost, resume, live=True)
    _require(any(r.startswith("critical:lost-state") for r in verdict.reasons), "lost state not caught")

    print("live_agentic_reliability_smoke: ok")


if __name__ == "__main__":
    asyncio.run(_main())
