from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from maya_core.reliability_incident_schema import INCIDENT_PATH, REASON_CODES, SUBSYSTEMS, OperationalIncident, normalize_enum
from maya_core.reliability_incident_store import load_incidents, resolve_incident


def resolve_open_incidents(
    *,
    subsystem: str,
    reason_codes: set[str] | tuple[str, ...] | list[str] | None = None,
    recovery_status: str,
    path: Path = INCIDENT_PATH,
    source_of_truth_checked: bool | None = None,
    source_of_truth_result: str = "",
    user_visible_message: str = "",
    detail: str = "",
    now: datetime | None = None,
) -> list[OperationalIncident]:
    """Resolve matching open incidents, including ones opened before a restart."""
    normalized_subsystem = normalize_enum(subsystem, SUBSYSTEMS)
    normalized_reasons = {normalize_enum(reason, REASON_CODES) for reason in (reason_codes or ())}
    resolved: list[OperationalIncident] = []
    for incident in list(load_incidents(path)):
        if incident.status != "open" or incident.subsystem != normalized_subsystem:
            continue
        if normalized_reasons and incident.reason_code not in normalized_reasons:
            continue
        updated = resolve_incident(
            incident.incident_id,
            recovery_status=recovery_status,
            path=path,
            source_of_truth_checked=source_of_truth_checked,
            source_of_truth_result=source_of_truth_result,
            user_visible_message=user_visible_message,
            detail=detail,
            now=now,
        )
        if updated is not None:
            resolved.append(updated)
    return resolved


def safe_resolve_open_incidents(*args: Any, **kwargs: Any) -> list[OperationalIncident]:
    try:
        return resolve_open_incidents(*args, **kwargs)
    except Exception:
        logging.getLogger("maya.reliability.incidents").debug("operational incident bulk resolution failed", exc_info=True)
        return []
