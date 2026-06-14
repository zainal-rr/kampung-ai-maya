"""Routine, automation, and weekly-memory projections for the Maya UI."""

from __future__ import annotations

import sqlite3
from typing import Any

from .readers_common import connect_ro, table_exists
from .state_reader import _safe


def _rows(conn: sqlite3.Connection, table: str, query: str, args: tuple = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in _safe(conn, table, query, args)]


def automations_snapshot() -> dict[str, Any]:
    with connect_ro() as conn:
        routines = _rows(
            conn,
            "routines",
            "SELECT id, name, kind, channel, local_time, weekday, active, autonomy_mode, "
            "last_run_key, updated_at FROM routines ORDER BY active DESC, local_time ASC",
        )
        weekly = _rows(
            conn,
            "weekly_memory_runs",
            "SELECT run_key, trigger_source, status, started_at, completed_at, "
            "provider_calls, canonical_saved, canonical_rejected, error "
            "FROM weekly_memory_runs ORDER BY id DESC LIMIT 8",
        )
        nightly = _rows(
            conn,
            "nightly_consolidation_runs",
            "SELECT run_key, status, episodes, saved, rejected, links_recorded, "
            "provider_calls, skip_reason, started_at, completed_at "
            "FROM nightly_consolidation_runs ORDER BY id DESC LIMIT 8",
        )
        routine_count = conn.execute("SELECT COUNT(*) FROM routines").fetchone()[0] if table_exists(conn, "routines") else 0
    return {
        "routines": routines,
        "weekly_memory": weekly,
        "nightly_consolidation": nightly,
        "counts": {
            "routines": routine_count,
            "active": sum(1 for item in routines if item.get("active")),
            "weekly_failures": sum(1 for item in weekly if item.get("status") == "failed"),
            "nightly_failures": sum(1 for item in nightly if item.get("status") == "failed"),
        },
        "launchd": {
            "status": "external",
            "detail": "launchd ownership is shown from run evidence; suspend/resume stays in chat until Phase 3.",
        },
    }


def artifact_quality_snapshot(limit: int = 20) -> dict[str, Any]:
    with connect_ro() as conn:
        sessions = _rows(
            conn,
            "artifact_sessions",
            "SELECT channel, artifact_type, path, short_name, title, topic, revision, "
            "status, updated_at, expires_at FROM artifact_sessions "
            "ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        )
        reviews = _rows(
            conn,
            "artifact_reviews",
            "SELECT artifact_type, topic, reviewer_model, passed, review_text, created_at "
            "FROM artifact_reviews ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        disagreements = _rows(
            conn,
            "qa_disagreement_events",
            "SELECT * FROM qa_disagreement_events ORDER BY id DESC LIMIT ?",
            (limit,),
        )
    return {
        "sessions": sessions,
        "reviews": [
            {
                **item,
                "review_text": str(item.get("review_text") or "")[:520],
                "reviewer_model": "The Steward",
            }
            for item in reviews
        ],
        "disagreements": disagreements,
    }


def memory_audit_snapshot(limit: int = 40) -> dict[str, Any]:
    with connect_ro() as conn:
        events = _rows(
            conn,
            "memory_audit_events",
            "SELECT event_type, memory_id, subject_key, status_before, status_after, "
            "source_channel, source_ref, run_id, content_hash, content_preview, created_at "
            "FROM memory_audit_events ORDER BY id DESC LIMIT ?",
            (limit,),
        )
    return {"events": events}
