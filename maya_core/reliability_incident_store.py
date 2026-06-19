from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from maya_core.reliability_incident_schema import (
    DEFAULT_BURST_WINDOW_SECONDS,
    FAILURE_CLASSES,
    INCIDENT_PATH,
    INCIDENT_STATUSES,
    REASON_CODES,
    RECOVERY_STATUSES,
    SUBSYSTEMS,
    OperationalIncident,
    burst_key,
    format_time,
    normalize_enum,
    now_iso,
    parse_time,
    worst_recovery_status,
)


def load_incidents(path: Path = INCIDENT_PATH) -> list[OperationalIncident]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = payload.get("incidents", []) if isinstance(payload, dict) else []
    incidents: list[OperationalIncident] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            incidents.append(OperationalIncident(**_incident_defaults(row)))
        except TypeError:
            continue
    return incidents


def save_incidents(incidents: list[OperationalIncident], path: Path = INCIDENT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": now_iso(),
        "schema": "operational_incidents.v1",
        "incidents": [asdict(incident) for incident in incidents],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), "utf-8")


def record_incident(
    *,
    subsystem: str,
    failure_class: str,
    reason_code: str,
    operation: str,
    source: str,
    path: Path = INCIDENT_PATH,
    source_of_truth_checked: bool = False,
    source_of_truth_result: str = "",
    user_visible_message: str = "",
    recovery_status: str = "not_attempted",
    safety_touching: bool = False,
    irreversible: bool = False,
    external_effect: bool = False,
    run_id: str = "",
    session_id: str = "",
    work_id: str = "",
    bot_id: str = "",
    detail: str = "",
    burst_window_seconds: int = DEFAULT_BURST_WINDOW_SECONDS,
    now: datetime | None = None,
) -> OperationalIncident:
    timestamp = format_time(now)
    normalized = _normalized_fields(subsystem, failure_class, reason_code, recovery_status)
    key = burst_key(
        normalized["subsystem"],
        normalized["reason_code"],
        operation,
        session_id=session_id,
        run_id=run_id,
        work_id=work_id,
        bot_id=bot_id,
    )
    incidents = load_incidents(path)
    existing_index = _find_burst_index(incidents, key, timestamp, burst_window_seconds)
    if existing_index is not None:
        incident = _update_burst(
            incidents[existing_index],
            timestamp,
            normalized["recovery_status"],
            source_of_truth_checked=source_of_truth_checked,
            source_of_truth_result=source_of_truth_result,
            user_visible_message=user_visible_message,
            safety_touching=safety_touching,
            irreversible=irreversible,
            external_effect=external_effect,
            detail=detail,
        )
        incidents[existing_index] = incident
        save_incidents(incidents, path)
        return incident
    incident = _new_incident(
        normalized,
        timestamp,
        key,
        operation=operation,
        source=source,
        source_of_truth_checked=source_of_truth_checked,
        source_of_truth_result=source_of_truth_result,
        user_visible_message=user_visible_message,
        safety_touching=safety_touching,
        irreversible=irreversible,
        external_effect=external_effect,
        run_id=run_id,
        session_id=session_id,
        work_id=work_id,
        bot_id=bot_id,
        detail=detail,
    )
    incidents.append(incident)
    save_incidents(incidents, path)
    return incident


def safe_record_incident(**kwargs: Any) -> OperationalIncident | None:
    try:
        return record_incident(**kwargs)
    except Exception:
        logging.getLogger("maya.reliability.incidents").debug("operational incident logging failed", exc_info=True)
        return None


def resolve_incident(
    incident_id: str,
    *,
    recovery_status: str,
    path: Path = INCIDENT_PATH,
    source_of_truth_checked: bool | None = None,
    source_of_truth_result: str = "",
    user_visible_message: str = "",
    detail: str = "",
    now: datetime | None = None,
) -> OperationalIncident | None:
    timestamp = format_time(now)
    normalized_recovery = normalize_enum(recovery_status, RECOVERY_STATUSES)
    incidents = load_incidents(path)
    for index, incident in enumerate(incidents):
        if incident.incident_id != incident_id:
            continue
        payload = asdict(incident)
        payload.update(
            {
                "last_seen": timestamp,
                "resolved_at": timestamp,
                "status": "resolved",
                "source_of_truth_checked": incident.source_of_truth_checked if source_of_truth_checked is None else bool(source_of_truth_checked),
                "source_of_truth_result": source_of_truth_result or incident.source_of_truth_result,
                "user_visible_message": user_visible_message or incident.user_visible_message,
                "recovery_status": worst_recovery_status(incident.recovery_status, normalized_recovery),
                "detail": detail or incident.detail,
            }
        )
        updated = OperationalIncident(**payload)
        incidents[index] = updated
        save_incidents(incidents, path)
        return updated
    return None


def safe_resolve_incident(*args: Any, **kwargs: Any) -> OperationalIncident | None:
    try:
        return resolve_incident(*args, **kwargs)
    except Exception:
        logging.getLogger("maya.reliability.incidents").debug("operational incident resolution failed", exc_info=True)
        return None




def _normalized_fields(subsystem: str, failure_class: str, reason_code: str, recovery_status: str) -> dict[str, str]:
    return {
        "subsystem": normalize_enum(subsystem, SUBSYSTEMS),
        "failure_class": normalize_enum(failure_class, FAILURE_CLASSES),
        "reason_code": normalize_enum(reason_code, REASON_CODES),
        "recovery_status": normalize_enum(recovery_status, RECOVERY_STATUSES),
    }


def _new_incident(
    normalized: dict[str, str],
    timestamp: str,
    key: str,
    *,
    operation: str,
    source: str,
    source_of_truth_checked: bool,
    source_of_truth_result: str,
    user_visible_message: str,
    safety_touching: bool,
    irreversible: bool,
    external_effect: bool,
    run_id: str,
    session_id: str,
    work_id: str,
    bot_id: str,
    detail: str,
) -> OperationalIncident:
    return OperationalIncident(
        incident_id=str(uuid.uuid4()),
        first_seen=timestamp,
        last_seen=timestamp,
        resolved_at="",
        status="open",
        operation=str(operation or "unknown"),
        source=str(source or "unknown"),
        source_of_truth_checked=bool(source_of_truth_checked),
        source_of_truth_result=str(source_of_truth_result or ""),
        user_visible_message=str(user_visible_message or ""),
        safety_touching=bool(safety_touching),
        irreversible=bool(irreversible),
        external_effect=bool(external_effect),
        run_id=str(run_id or ""),
        session_id=str(session_id or ""),
        work_id=str(work_id or ""),
        bot_id=str(bot_id or ""),
        burst_key=key,
        burst_count=1,
        detail=str(detail or ""),
        **normalized,
    )


def _update_burst(incident: OperationalIncident, timestamp: str, recovery_status: str, **updates: Any) -> OperationalIncident:
    payload = asdict(incident)
    payload.update(
        {
            "last_seen": timestamp,
            "resolved_at": "",
            "status": "open",
            "source_of_truth_checked": incident.source_of_truth_checked or bool(updates["source_of_truth_checked"]),
            "source_of_truth_result": updates["source_of_truth_result"] or incident.source_of_truth_result,
            "user_visible_message": updates["user_visible_message"] or incident.user_visible_message,
            "recovery_status": worst_recovery_status(incident.recovery_status, recovery_status),
            "safety_touching": incident.safety_touching or bool(updates["safety_touching"]),
            "irreversible": incident.irreversible or bool(updates["irreversible"]),
            "external_effect": incident.external_effect or bool(updates["external_effect"]),
            "detail": updates["detail"] or incident.detail,
            "burst_count": incident.burst_count + 1,
        }
    )
    return OperationalIncident(**payload)


def _find_burst_index(incidents: list[OperationalIncident], key: str, timestamp: str, window_seconds: int) -> int | None:
    current = parse_time(timestamp)
    for index in range(len(incidents) - 1, -1, -1):
        incident = incidents[index]
        if incident.burst_key != key:
            continue
        if abs((current - parse_time(incident.last_seen)).total_seconds()) <= max(0, window_seconds):
            return index
    return None


def _incident_defaults(row: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "incident_id": str(row.get("incident_id") or uuid.uuid4()),
        "first_seen": str(row.get("first_seen") or now_iso()),
        "last_seen": str(row.get("last_seen") or row.get("first_seen") or now_iso()),
        "resolved_at": str(row.get("resolved_at") or ""),
        "status": normalize_enum(str(row.get("status") or "open"), INCIDENT_STATUSES),
        **_normalized_fields(
            str(row.get("subsystem") or "unknown"),
            str(row.get("failure_class") or "unknown"),
            str(row.get("reason_code") or "unknown"),
            str(row.get("recovery_status") or "unknown"),
        ),
        "operation": str(row.get("operation") or "unknown"),
        "source": str(row.get("source") or "unknown"),
        "source_of_truth_checked": bool(row.get("source_of_truth_checked", False)),
        "source_of_truth_result": str(row.get("source_of_truth_result") or ""),
        "user_visible_message": str(row.get("user_visible_message") or ""),
        "safety_touching": bool(row.get("safety_touching", False)),
        "irreversible": bool(row.get("irreversible", False)),
        "external_effect": bool(row.get("external_effect", False)),
        "run_id": str(row.get("run_id") or ""),
        "session_id": str(row.get("session_id") or ""),
        "work_id": str(row.get("work_id") or ""),
        "bot_id": str(row.get("bot_id") or ""),
        "burst_key": str(row.get("burst_key") or ""),
        "burst_count": int(row.get("burst_count") or 1),
        "detail": str(row.get("detail") or ""),
    }
    if not normalized["burst_key"]:
        normalized["burst_key"] = burst_key(normalized["subsystem"], normalized["reason_code"], normalized["operation"])
    return normalized
