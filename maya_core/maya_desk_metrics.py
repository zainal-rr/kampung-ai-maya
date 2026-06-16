from __future__ import annotations

from collections import Counter

import aiosqlite

from browser_benchmark import format_browser_benchmark
from maya_core.reliability_scorecard import format_reliability_scorecard


async def trace_metric_items(db_path: str) -> list[str]:
    await _ensure_events_exists(db_path)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            SELECT event_type, COUNT(*)
            FROM maya_events
            WHERE created_at >= datetime('now', '-30 days')
            GROUP BY event_type
            """
        )
        rows = await cursor.fetchall()
    counts = Counter({str(event_type): int(count) for event_type, count in rows})
    if not counts:
        return ["No Maya event trace rows found in the last 30 days."]
    return [f"{name}: {count}" for name, count in sorted(counts.items())]


async def failure_metric_items(db_path: str) -> list[str]:
    await _ensure_events_exists(db_path)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            SELECT event_type, summary, created_at
            FROM maya_events
            WHERE created_at >= datetime('now', '-30 days')
              AND (
                lower(summary) LIKE '%fail%' OR
                lower(summary) LIKE '%error%' OR
                lower(summary) LIKE '%reject%'
              )
            ORDER BY id DESC
            LIMIT 10
            """
        )
        rows = await cursor.fetchall()
    if not rows:
        return ["No failure-like trace events found in the last 30 days."]
    return [f"{created_at} {event_type}: {summary}" for event_type, summary, created_at in rows]


def reliability_metric_text() -> str:
    return format_reliability_scorecard()


def browser_benchmark_text() -> str:
    return format_browser_benchmark()


async def _ensure_events_exists(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS maya_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                run_id TEXT DEFAULT '',
                event_type TEXT NOT NULL,
                actor TEXT DEFAULT 'maya',
                summary TEXT DEFAULT '',
                payload_json TEXT DEFAULT '{}',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()
