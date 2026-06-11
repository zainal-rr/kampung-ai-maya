"""Cursor-based tail over harness_events + route_events (read-only).

Implements the feed side of SSE_PROTOCOL.md v1: cursor = (he, re) row ids,
items are normalized dicts whose unknown-field tolerance is the client's job.
"""

from __future__ import annotations

import sqlite3
from .readers_common import (
    PROTO,
    connect_ro,
    has_column,
    mask_lanes,
    schema_version_of,
    table_exists,
)


def _harness_item(row: sqlite3.Row, sv: bool) -> dict:
    summary = f"{row['event']} — {row['details']}" if row["details"] else row["event"]
    return {
        "proto": PROTO,
        "schema_version": schema_version_of(row, sv),
        "type": "harness",
        "id": int(row["id"]),
        "ts": row["created_at"],
        "run_id": row["run_id"],
        "summary": mask_lanes(summary),
        "lane": None,
    }


def _route_item(row: sqlite3.Row, sv: bool) -> dict:
    return {
        "proto": PROTO,
        "schema_version": schema_version_of(row, sv),
        "type": "route",
        "id": int(row["id"]),
        "ts": row["created_at"],
        "run_id": None,
        "summary": mask_lanes(f"{row['input_type']} → {row['reason']}"),
        "lane": mask_lanes(row["lane"]),
        "cost_recorded": bool(row["cost_recorded"]),
    }


def latest_cursor() -> tuple[int, int]:
    """Current max ids — used so a fresh client starts at 'now minus N'."""
    with connect_ro() as conn:
        he = re_ = 0
        if table_exists(conn, "harness_events"):
            he = conn.execute("SELECT COALESCE(MAX(id),0) FROM harness_events").fetchone()[0]
        if table_exists(conn, "route_events"):
            re_ = conn.execute("SELECT COALESCE(MAX(id),0) FROM route_events").fetchone()[0]
        return int(he), int(re_)


def read_after(he: int, re_: int, limit: int = 100) -> tuple[list[dict], int, int]:
    """Return feed items with id greater than the cursor, oldest first."""
    items: list[dict] = []
    with connect_ro() as conn:
        if table_exists(conn, "harness_events"):
            sv = has_column(conn, "harness_events", "schema_version")
            rows = conn.execute(
                "SELECT * FROM harness_events WHERE id>? ORDER BY id ASC LIMIT ?",
                (he, limit),
            ).fetchall()
            for row in rows:
                items.append(_harness_item(row, sv))
                he = max(he, int(row["id"]))
        if table_exists(conn, "route_events"):
            sv = has_column(conn, "route_events", "schema_version")
            rows = conn.execute(
                "SELECT * FROM route_events WHERE id>? ORDER BY id ASC LIMIT ?",
                (re_, limit),
            ).fetchall()
            for row in rows:
                items.append(_route_item(row, sv))
                re_ = max(re_, int(row["id"]))
    items.sort(key=lambda item: (item["ts"] or "", item["id"]))
    return items, he, re_


def read_recent(limit: int = 30) -> tuple[list[dict], int, int]:
    """Last N items across both tables plus the cursor to resume from."""
    items: list[dict] = []
    with connect_ro() as conn:
        he = re_ = 0
        if table_exists(conn, "harness_events"):
            sv = has_column(conn, "harness_events", "schema_version")
            rows = conn.execute(
                "SELECT * FROM harness_events ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            items.extend(_harness_item(r, sv) for r in rows)
            he = max((int(r["id"]) for r in rows), default=0)
        if table_exists(conn, "route_events"):
            sv = has_column(conn, "route_events", "schema_version")
            rows = conn.execute(
                "SELECT * FROM route_events ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            items.extend(_route_item(r, sv) for r in rows)
            re_ = max((int(r["id"]) for r in rows), default=0)
        he_max, re_max = latest_cursor()
        he, re_ = max(he, he_max), max(re_, re_max)
    items.sort(key=lambda item: (item["ts"] or "", item["id"]))
    return items[-limit:], he, re_
