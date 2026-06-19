from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from maya_core.reliability_incidents import (
    derive_severity,
    effective_recovery_status,
    format_incident_report,
    load_incidents,
    record_artifact_postcondition,
    record_browser_bridge_preflight_status,
    record_incident,
    record_source_of_truth_check,
    recovery_split,
    resolve_open_incidents,
    resolve_incident,
    safe_record_incident,
    top_offenders,
)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-incidents-") as tmp:
        path = Path(tmp) / "incidents.json"
        opened = record_incident(
            path=path,
            subsystem="browser_bridge",
            failure_class="disconnected",
            reason_code="bridge_no_client",
            operation="browser_search",
            source="smoke",
            session_id="s1",
            now=_at(0),
        )
        rows = load_incidents(path)
        _require(len(rows) == 1, "incident not inserted")
        _require(rows[0].status == "open", "new incident not open")
        _require(rows[0].recovery_status == "not_attempted", "new incident did not start unresolved")
        _require(effective_recovery_status(rows[0]) == "degraded", "open incidents must rank at least degraded")

        recovered = resolve_incident(opened.incident_id, path=path, recovery_status="recovered", now=_at(10))
        _require(recovered is not None and recovered.status == "resolved", "incident did not resolve")
        _require(bool(recovered.resolved_at), "resolved incident missing timestamp")
        _require(derive_severity(recovered) == 2, "recovered disconnect should be severity 2")

        wedged = resolve_incident(opened.incident_id, path=path, recovery_status="wedged", now=_at(20))
        _require(wedged is not None and wedged.recovery_status == "wedged", "worst recovery did not win")
        _require(derive_severity(wedged) == 4, "wedged incident did not promote severity")

        burst = record_incident(
            path=path,
            subsystem="browser_bridge",
            failure_class="disconnected",
            reason_code="bridge_no_client",
            operation="browser_search",
            source="smoke",
            session_id="s1",
            recovery_status="degraded",
            now=_at(25),
        )
        _require(burst.incident_id == opened.incident_id, "same burst did not dedupe")
        _require(burst.burst_count == 2, "burst count did not increment")
        _require(burst.recovery_status == "wedged", "burst did not preserve worst recovery")
        _require(burst.status == "open" and not burst.resolved_at, "new burst event did not reopen incident")

        unknown = record_incident(
            path=path,
            subsystem="made_up_subsystem",
            failure_class="made_up_failure",
            reason_code="free text reason",
            operation="free_text",
            source="smoke",
            now=_at(400),
        )
        _require(unknown.subsystem == "unknown", "unknown subsystem did not normalize")
        _require(unknown.failure_class == "unknown", "unknown failure class did not normalize")
        _require(unknown.reason_code == "unknown", "unknown reason did not normalize")

        artifact = record_artifact_postcondition(
            path=path,
            claimed_done=True,
            artifact_exists=False,
            operation="make_word",
            run_id="r-artifact",
            user_visible_message="I made the document.",
        )
        _require(artifact is not None, "artifact postcondition did not emit incident")
        _require(artifact.failure_class == "false_success_risk", "artifact missing must be false_success_risk")
        _require(derive_severity(artifact) == 5, "safety-touching false success must be severity 5")

        mismatch = record_source_of_truth_check(
            path=path,
            operation="meet_join_reuse",
            cached_status="live",
            source_status="done",
            checked=True,
            subsystem="recall_meet",
            session_id="meet-1",
            bot_id="bot-1",
            external_effect=True,
        )
        _require(mismatch is not None, "source-of-truth mismatch did not emit")
        _require(mismatch.failure_class == "source_of_truth_mismatch", "wrong mismatch class")
        _require(derive_severity(mismatch) == 5, "external source-of-truth mismatch should be severity 5")

        stale = record_source_of_truth_check(
            path=path,
            operation="meet_status",
            cached_status="live",
            source_status="",
            checked=False,
            subsystem="status",
            session_id="meet-2",
        )
        _require(stale is not None and stale.failure_class == "stale_state", "unchecked source-of-truth must emit stale_state")

        bridge = record_browser_bridge_preflight_status(
            {"ready": False, "client_connected": False, "reason_code": "browser_bridge_unavailable"},
            path=path,
            operation="voice_browser_command",
        )
        _require(bridge is not None and bridge.reason_code == "bridge_no_client", "browser detector did not map failed preflight")
        stale_socket = record_browser_bridge_preflight_status(
            {"ready": False, "client_connected": True, "reason_code": "stale_ping"},
            path=path,
            operation="voice_browser_command",
        )
        _require(
            stale_socket is not None and stale_socket.reason_code == "bridge_stale_ping",
            "connected-but-not-ready bridge must still emit a stale-ping incident",
        )
        recovered_bridge = resolve_open_incidents(
            path=path,
            subsystem="browser_bridge",
            reason_codes=("bridge_no_client",),
            recovery_status="recovered",
            source_of_truth_checked=True,
            source_of_truth_result="ready",
            user_visible_message="Browser bridge is ready.",
        )
        _require(
            any(row.incident_id == bridge.incident_id and row.status == "resolved" for row in recovered_bridge),
            "healthy bridge monitor did not resolve prior open browser incidents",
        )
        no_bridge = record_browser_bridge_preflight_status(
            {"ready": True, "client_connected": True, "reason_code": "connected"},
            path=path,
            operation="voice_browser_command",
        )
        _require(no_bridge is None, "healthy browser preflight should not emit")

        bad_path = Path(tmp)
        failed = safe_record_incident(
            path=bad_path,
            subsystem="runtime",
            failure_class="exception",
            reason_code="runtime_exception",
            operation="x",
            source="smoke",
        )
        _require(failed is None, "safe logging did not fail open")

        rows = load_incidents(path)
        offenders = top_offenders(rows)
        _require(offenders[0].impact_score >= offenders[-1].impact_score, "top offenders not impact sorted")
        _require(offenders[0].max_severity >= 4, "serious incident not surfaced near top")
        split = recovery_split(rows)
        _require(split["wedged"] >= 1 and split["degraded"] >= 1, f"split missing states: {split}")
        report = format_incident_report(rows)
        _require("Top offenders by impact" in report, "top-offender report missing")
        _require("recovered/degraded/wedged" in report, "recovery split not visible")
        _require("Open/unresolved incidents" in report, "open incidents not surfaced")
        _require("Serious but rare" in report, "serious-but-rare section missing")
        empty = format_incident_report([])
        _require("no incidents observed" in empty.lower(), "empty report must say no incidents observed")
        _require("reliable" not in empty.lower(), "empty report must not call subsystem reliable")

    print("reliability_incident_ledger_smoke: ok")


def _at(offset_seconds: int) -> datetime:
    return datetime(2026, 6, 19, 0, 0, 0, tzinfo=UTC) + timedelta(seconds=offset_seconds)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
