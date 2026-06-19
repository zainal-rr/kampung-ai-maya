from __future__ import annotations

from pathlib import Path
from typing import Any

from maya_core.reliability_incident_schema import INCIDENT_PATH, OperationalIncident
from maya_core.reliability_incident_store import safe_record_incident


def record_artifact_postcondition(
    *,
    claimed_done: bool,
    artifact_exists: bool,
    qa_passed: bool = True,
    context_matches: bool = True,
    operation: str,
    path: Path = INCIDENT_PATH,
    run_id: str = "",
    work_id: str = "",
    user_visible_message: str = "",
) -> OperationalIncident | None:
    if claimed_done and not artifact_exists:
        return safe_record_incident(
            path=path,
            subsystem="artifact",
            failure_class="false_success_risk",
            reason_code="artifact_missing_after_done",
            operation=operation,
            source="artifact_postcondition",
            source_of_truth_checked=True,
            source_of_truth_result="artifact_missing",
            user_visible_message=user_visible_message,
            safety_touching=True,
            run_id=run_id,
            work_id=work_id,
        )
    if not context_matches:
        return safe_record_incident(
            path=path,
            subsystem="artifact",
            failure_class="false_success_risk",
            reason_code="artifact_context_mismatch",
            operation=operation,
            source="artifact_postcondition",
            source_of_truth_checked=True,
            source_of_truth_result="context_mismatch",
            user_visible_message=user_visible_message,
            safety_touching=True,
            run_id=run_id,
            work_id=work_id,
        )
    if not qa_passed:
        return safe_record_incident(
            path=path,
            subsystem="artifact",
            failure_class="qa_failed",
            reason_code="artifact_qa_failed",
            operation=operation,
            source="artifact_postcondition",
            source_of_truth_checked=True,
            source_of_truth_result="qa_failed",
            user_visible_message=user_visible_message,
            run_id=run_id,
            work_id=work_id,
        )
    return None


def record_source_of_truth_check(
    *,
    operation: str,
    cached_status: str,
    source_status: str,
    checked: bool,
    path: Path = INCIDENT_PATH,
    subsystem: str = "status",
    session_id: str = "",
    bot_id: str = "",
    external_effect: bool = False,
    user_visible_message: str = "",
) -> OperationalIncident | None:
    if not checked:
        return safe_record_incident(
            path=path,
            subsystem=subsystem,
            failure_class="stale_state",
            reason_code="source_of_truth_not_checked",
            operation=operation,
            source="source_of_truth_check",
            source_of_truth_checked=False,
            source_of_truth_result="not_checked",
            user_visible_message=user_visible_message,
            session_id=session_id,
            bot_id=bot_id,
            external_effect=external_effect,
        )
    if str(cached_status) != str(source_status):
        return safe_record_incident(
            path=path,
            subsystem=subsystem,
            failure_class="source_of_truth_mismatch",
            reason_code="source_of_truth_disagreed",
            operation=operation,
            source="source_of_truth_check",
            source_of_truth_checked=True,
            source_of_truth_result=f"cached={cached_status};source={source_status}",
            user_visible_message=user_visible_message,
            session_id=session_id,
            bot_id=bot_id,
            external_effect=external_effect,
        )
    return None


def record_browser_bridge_preflight_status(
    status: dict[str, Any],
    *,
    operation: str = "browser_bridge_preflight",
    path: Path = INCIDENT_PATH,
    session_id: str = "",
) -> OperationalIncident | None:
    if bool(status.get("ready")):
        return None
    raw_reason = str(status.get("reason_code") or "")
    reason = _browser_reason(raw_reason, status)
    return safe_record_incident(
        path=path,
        subsystem="browser_bridge",
        failure_class="disconnected",
        reason_code=reason,
        operation=operation,
        source="browser_bridge_preflight",
        source_of_truth_checked=True,
        source_of_truth_result=raw_reason or "not_ready",
        user_visible_message="Browser bridge is not connected.",
        session_id=session_id,
    )


def _browser_reason(raw_reason: str, status: dict[str, Any]) -> str:
    if raw_reason in {"not_started", "browser_bridge_unavailable"} and not status.get("client_connected"):
        return "bridge_no_client"
    if raw_reason in {"stale", "stale_ping", "bridge_stale_ping"}:
        return "bridge_stale_ping"
    return "bridge_preflight_failed"
