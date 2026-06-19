from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


INCIDENT_PATH = Path("logs") / "live_tests" / "operational_incidents.json"
DEFAULT_BURST_WINDOW_SECONDS = 300

SUBSYSTEMS = (
    "browser_bridge",
    "recall_meet",
    "telegram",
    "voice",
    "artifact",
    "agentic_loop",
    "memory",
    "provider",
    "status",
    "runtime",
    "unknown",
)

FAILURE_CLASSES = (
    "disconnected",
    "timeout",
    "stale_state",
    "source_of_truth_mismatch",
    "qa_failed",
    "false_success_risk",
    "provider_down",
    "delivery_failed",
    "loop_budget_exhausted",
    "checkpoint_lost",
    "exception",
    "unknown",
)

INCIDENT_STATUSES = ("open", "resolved")
RECOVERY_STATUSES = ("not_attempted", "recovered", "degraded", "wedged", "unknown")

REASON_CODES = (
    "bridge_no_client",
    "bridge_stale_ping",
    "bridge_preflight_failed",
    "recall_public_health_failed",
    "recall_join_failed",
    "recall_left_unexpectedly",
    "recall_status_mismatch",
    "recall_output_failed",
    "telegram_send_failed",
    "telegram_update_error",
    "voice_session_timeout",
    "voice_audio_error",
    "voice_provider_down",
    "artifact_missing_after_done",
    "artifact_qa_failed",
    "artifact_context_mismatch",
    "agentic_budget_exhausted",
    "agentic_provider_error",
    "agentic_checkpoint_lost",
    "stale_cached_live_state",
    "source_of_truth_not_checked",
    "source_of_truth_disagreed",
    "memory_recall_miss",
    "memory_write_failed",
    "provider_unavailable",
    "runtime_exception",
    "unknown",
)

RECOVERY_RANK = {
    "unknown": 0,
    "not_attempted": 1,
    "recovered": 2,
    "degraded": 3,
    "wedged": 4,
}


@dataclass(frozen=True)
class OperationalIncident:
    incident_id: str
    first_seen: str
    last_seen: str
    resolved_at: str
    status: str
    subsystem: str
    failure_class: str
    reason_code: str
    operation: str
    source: str
    source_of_truth_checked: bool
    source_of_truth_result: str
    user_visible_message: str
    recovery_status: str
    safety_touching: bool
    irreversible: bool
    external_effect: bool
    run_id: str
    session_id: str
    work_id: str
    bot_id: str
    burst_key: str
    burst_count: int
    detail: str = ""


@dataclass(frozen=True)
class IncidentOffender:
    subsystem: str
    failure_class: str
    reason_code: str
    incident_count: int
    burst_count: int
    max_severity: int
    impact_score: int
    recovered: int
    degraded: int
    wedged: int
    open_count: int


def normalize_enum(value: str, allowed: tuple[str, ...]) -> str:
    return value if value in allowed else "unknown"


def worst_recovery_status(left: str, right: str) -> str:
    left_normal = normalize_enum(left, RECOVERY_STATUSES)
    right_normal = normalize_enum(right, RECOVERY_STATUSES)
    return left_normal if RECOVERY_RANK[left_normal] >= RECOVERY_RANK[right_normal] else right_normal


def effective_recovery_status(incident: OperationalIncident) -> str:
    recovery = normalize_enum(incident.recovery_status, RECOVERY_STATUSES)
    if incident.status == "open" and RECOVERY_RANK[recovery] < RECOVERY_RANK["degraded"]:
        return "degraded"
    return recovery


def derive_severity(incident: OperationalIncident) -> int:
    recovery = effective_recovery_status(incident)
    if incident.failure_class == "false_success_risk" and (incident.irreversible or incident.safety_touching):
        return 5
    if incident.failure_class == "source_of_truth_mismatch" and incident.external_effect:
        return 5
    if recovery == "wedged":
        return 4
    if incident.failure_class == "stale_state" and incident.reason_code in {
        "stale_cached_live_state",
        "source_of_truth_not_checked",
        "source_of_truth_disagreed",
    }:
        return 4
    if incident.subsystem == "artifact" and incident.reason_code in {
        "artifact_missing_after_done",
        "artifact_context_mismatch",
    }:
        return 4
    if incident.status == "open":
        return 3
    if incident.failure_class in {"provider_down", "delivery_failed", "checkpoint_lost", "exception"}:
        return 3
    if recovery == "degraded":
        return 1
    if recovery == "recovered" and incident.failure_class in {"disconnected", "timeout"}:
        return 2
    if incident.failure_class in {"qa_failed", "loop_budget_exhausted"}:
        return 2
    return 1


def burst_key(
    subsystem: str,
    reason_code: str,
    operation: str,
    *,
    session_id: str = "",
    run_id: str = "",
    work_id: str = "",
    bot_id: str = "",
) -> str:
    scope = session_id or run_id or work_id or bot_id or "global"
    return f"{subsystem}:{reason_code}:{operation or 'unknown'}:{scope}"


def now_iso() -> str:
    return format_time(None)


def format_time(value: datetime | None) -> str:
    when = value or datetime.now(UTC)
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return when.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_time(value: str) -> datetime:
    if not value:
        return datetime.now(UTC) - timedelta(days=3650)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(UTC) - timedelta(days=3650)
