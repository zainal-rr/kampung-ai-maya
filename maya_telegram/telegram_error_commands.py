from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

from maya_core.reliability_incident_schema import INCIDENT_PATH
from maya_core.reliability_incident_store import safe_record_incident
from maya_core.route_tracker import last_route_text
from maya_core.session_compactor import inspect_session_context
from maya_core.storage import get_history
from maya_telegram.telegram_delivery_log import latest_telegram_delivery_text
from maya_telegram.telegram_reliability_commands import RELIABILITY_NOTE_FIELDS, record_reliability_note
from maya_telegram.telegram_turn_log import latest_telegram_turn_text


ERROR_SNAPSHOT_PATH = Path("logs") / "live_tests" / "telegram_error_snapshots.json"

ERROR_INCIDENT_MAP = {
    "browser": ("browser_bridge", "unknown", "unknown"),
    "cost": ("provider", "unknown", "unknown"),
    "correction": ("runtime", "unknown", "unknown"),
    "delivery": ("telegram", "delivery_failed", "telegram_send_failed"),
    "false_done": ("artifact", "false_success_risk", "artifact_missing_after_done"),
    "memory": ("memory", "unknown", "memory_recall_miss"),
    "missed_reply": ("telegram", "timeout", "telegram_update_error"),
    "route": ("runtime", "unknown", "unknown"),
    "voice": ("voice", "timeout", "voice_session_timeout"),
}


async def error_text(db_path: str, args: str) -> str:
    category, note = _error_parts(args)
    if not note:
        return (
            "Error: use /error [category] <what failed>.\n"
            "Categories: correction, missed_reply, route, voice, memory, delivery, browser, cost, false_done."
        )
    snapshot = await _error_snapshot(db_path, category, note)
    snapshot_path = _store_error_snapshot(snapshot)
    soak_field = record_reliability_note(category, note)
    incident = _record_error_incident(category, note, snapshot)
    lines = [
        "Error:",
        "Failure recorded.",
        f"Category: {category} ({soak_field})",
        f"Snapshot: {snapshot['snapshot_id']}",
        "Fresh topic started.",
    ]
    if incident:
        lines.append(f"Incident: {incident.incident_id}")
    if snapshot_path:
        lines.append(f"Evidence file: {snapshot_path}")
    return "\n".join(lines)


def _error_parts(args: str) -> tuple[str, str]:
    cleaned = args.strip()
    if not cleaned:
        return "correction", ""
    first, _, rest = cleaned.partition(" ")
    normalized = first.lower().strip().replace("-", "_")
    if normalized in RELIABILITY_NOTE_FIELDS and rest.strip():
        return normalized, rest.strip()
    return "correction", cleaned


async def _error_snapshot(db_path: str, category: str, note: str) -> dict[str, object]:
    return {
        "snapshot_id": str(uuid.uuid4()),
        "created_at": _now(),
        "source": "telegram_error_command",
        "category": category,
        "note": note,
        "recent_history": await get_history(db_path, 1, limit=8),
        "last_turn": await latest_telegram_turn_text(db_path),
        "last_delivery": await latest_telegram_delivery_text(db_path),
        "last_route": await last_route_text(db_path),
        "context_window": await inspect_session_context(db_path),
    }


def _store_error_snapshot(snapshot: dict[str, object]) -> str:
    path = _error_snapshot_path()
    try:
        rows = _load_snapshots(path)
        rows.append(snapshot)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"updated_at": _now(), "snapshots": rows[-200:]}, indent=2), "utf-8")
        return str(path)
    except Exception:
        return ""


def _record_error_incident(category: str, note: str, snapshot: dict[str, object]):
    subsystem, failure_class, reason_code = ERROR_INCIDENT_MAP.get(category, ERROR_INCIDENT_MAP["correction"])
    return safe_record_incident(
        subsystem=subsystem,
        failure_class=failure_class,
        reason_code=reason_code,
        operation="telegram_error_report",
        source="telegram_error_command",
        path=_incident_path(),
        recovery_status="not_attempted",
        user_visible_message="Owner reported a Maya failure with /error.",
        run_id=str(snapshot["snapshot_id"]),
        session_id=str(snapshot["snapshot_id"]),
        detail=json.dumps({"note": note, "snapshot_id": snapshot["snapshot_id"]})[:4000],
    )


def _load_snapshots(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = payload.get("snapshots", []) if isinstance(payload, dict) else []
    return [row for row in rows if isinstance(row, dict)]


def _error_snapshot_path() -> Path:
    override = os.environ.get("MAYA_ERROR_SNAPSHOT_PATH", "").strip()
    return Path(override) if override else ERROR_SNAPSHOT_PATH


def _incident_path() -> Path:
    override = os.environ.get("MAYA_OPERATIONAL_INCIDENT_PATH", "").strip()
    return Path(override) if override else INCIDENT_PATH


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
