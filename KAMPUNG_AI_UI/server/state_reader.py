"""Desk snapshot queries (read-only, tolerant of missing tables).

Every function returns plain JSON-able dicts. A missing table yields an empty
section, never an exception — the UI renders what exists.
"""

from __future__ import annotations

import sqlite3
from .readers_common import connect_ro, mask_lane_key, mask_lanes, table_exists


def _safe(conn: sqlite3.Connection, table: str, query: str, args: tuple = ()) -> list[sqlite3.Row]:
    if not table_exists(conn, table):
        return []
    try:
        return conn.execute(query, args).fetchall()
    except sqlite3.Error:
        return []


def pending_approvals(conn: sqlite3.Connection, limit: int = 10) -> list[dict]:
    rows = _safe(
        conn,
        "harness_approvals",
        "SELECT * FROM harness_approvals WHERE status IN ('pending','waiting') "
        "ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    return [
        {
            "id": row["id"],
            "run_id": row["run_id"],
            "action": mask_lanes(row["action"]),
            "details": mask_lanes(row["details"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def recent_runs(conn: sqlite3.Connection, limit: int = 8) -> list[dict]:
    rows = _safe(
        conn,
        "harness_runs",
        "SELECT run_id, thread_id, channel, workflow_type, goal, status, "
        "current_step, updated_at FROM harness_runs ORDER BY updated_at DESC LIMIT ?",
        (limit,),
    )
    return [
        {
            "run_id": row["run_id"],
            "thread_id": row["thread_id"],
            "channel": row["channel"],
            "workflow_type": row["workflow_type"],
            "goal": mask_lanes((row["goal"] or "")[:140]),
            "status": row["status"],
            "current_step": row["current_step"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def canary_status(conn: sqlite3.Connection) -> list[dict]:
    rows = _safe(
        conn,
        "memory_canaries",
        "SELECT subject_key, expected_state, last_result, last_checked_at, "
        "failure_reason FROM memory_canaries ORDER BY canary_id",
    )
    return [
        {
            "subject_key": row["subject_key"],
            "expected_state": row["expected_state"],
            "last_result": row["last_result"],
            "last_checked_at": row["last_checked_at"],
            "failure_reason": row["failure_reason"],
        }
        for row in rows
    ]


def memory_summary(conn: sqlite3.Connection) -> dict:
    rows = _safe(
        conn,
        "canonical_memory_items",
        "SELECT status, COUNT(*) AS n FROM canonical_memory_items GROUP BY status",
    )
    by_status = {row["status"]: row["n"] for row in rows}
    pinned = _safe(
        conn,
        "canonical_memory_items",
        "SELECT COUNT(*) AS n FROM canonical_memory_items WHERE pinned=1",
    )
    return {
        "by_status": by_status,
        "pinned": pinned[0]["n"] if pinned else 0,
        "total": sum(by_status.values()),
    }


def usage_today(conn: sqlite3.Connection) -> list[dict]:
    rows = _safe(
        conn,
        "usage_events",
        "SELECT lane, COUNT(*) AS calls, SUM(units) AS units FROM usage_events "
        "WHERE date(created_at)=date('now') GROUP BY lane ORDER BY calls DESC LIMIT 12",
    )
    return [
        {"lane": mask_lane_key(row["lane"]), "calls": row["calls"], "units": row["units"]}
        for row in rows
    ]


def last_routes(conn: sqlite3.Connection, limit: int = 5) -> list[dict]:
    rows = _safe(
        conn,
        "route_events",
        "SELECT input_type, lane, reason, cost_recorded, created_at FROM route_events "
        "ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    return [
        {
            "input_type": row["input_type"],
            "lane": mask_lanes(row["lane"]),
            "reason": mask_lanes(row["reason"]),
            "cost_recorded": bool(row["cost_recorded"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def open_tasks(conn: sqlite3.Connection) -> dict:
    rows = _safe(
        conn,
        "tasks",
        "SELECT status, COUNT(*) AS n FROM tasks GROUP BY status",
    )
    return {row["status"]: row["n"] for row in rows}


def threads(conn: sqlite3.Connection, limit: int = 8) -> list[dict]:
    rows = _safe(
        conn,
        "harness_runs",
        "SELECT thread_id, MAX(updated_at) AS updated_at, COUNT(*) AS runs, "
        "MAX(CASE WHEN status IN ('running','waiting_approval','waiting_user','paused') "
        "THEN 1 ELSE 0 END) AS busy FROM harness_runs GROUP BY thread_id "
        "ORDER BY updated_at DESC LIMIT ?",
        (limit,),
    )
    return [
        {"thread_id": row["thread_id"], "updated_at": row["updated_at"],
         "runs": row["runs"], "busy": bool(row["busy"])}
        for row in rows
    ]


def memory_rows(limit: int = 40) -> list[dict]:
    with connect_ro() as conn:
        rows = _safe(
            conn,
            "canonical_memory_items",
            "SELECT subject_key, kind, status, pinned, reinforcement_count, "
            "updated_at, content, value FROM canonical_memory_items "
            "ORDER BY pinned DESC, updated_at DESC LIMIT ?",
            (limit,),
        )
    return [
        {
            "subject_key": row["subject_key"],
            "kind": row["kind"],
            "status": row["status"],
            "pinned": bool(row["pinned"]),
            "reinforced": row["reinforcement_count"],
            "updated_at": row["updated_at"],
            "preview": mask_lanes(((row["value"] or row["content"] or "")[:90])),
        }
        for row in rows
    ]


def artifacts_recent(limit: int = 25) -> list[dict]:
    with connect_ro() as conn:
        rows = _safe(
            conn,
            "harness_artifacts",
            "SELECT kind, path, summary, created_at, exists_status, delivery_status "
            "FROM harness_artifacts ORDER BY id DESC LIMIT ?",
            (limit,),
        )
    return [
        {
            "kind": row["kind"],
            "name": (row["path"] or "").rsplit("/", 1)[-1] or row["kind"],
            "summary": mask_lanes((row["summary"] or "")[:130]),
            "created_at": row["created_at"],
            "exists_status": row["exists_status"],
            "delivery_status": row["delivery_status"],
        }
        for row in rows
    ]


def desk_snapshot() -> dict:
    with connect_ro() as conn:
        return {
            "approvals": pending_approvals(conn),
            "runs": recent_runs(conn),
            "canaries": canary_status(conn),
            "memory": memory_summary(conn),
            "usage_today": usage_today(conn),
            "last_routes": last_routes(conn),
            "tasks": open_tasks(conn),
            "threads": threads(conn),
        }
