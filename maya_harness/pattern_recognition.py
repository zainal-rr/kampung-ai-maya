from __future__ import annotations

import json
import uuid
from typing import Any, Mapping

import aiosqlite

from maya_harness.pattern_recognition_schema import (
    MAX_RETRIEVED_PATTERNS,
    SUPERSESSION_VALUES,
    derive_episode_provenance,
    derive_method,
    derive_outcome,
    derive_situation_shape,
    normalize_method,
    normalize_outcome,
    normalize_provenance,
    normalize_situation_shape,
    pattern_fact_from_row,
    trust_tier_for,
)


async def init_pattern_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS harness_patterns (
                pattern_id TEXT PRIMARY KEY,
                task_category TEXT NOT NULL,
                source_type TEXT NOT NULL,
                goal_type TEXT NOT NULL,
                method_json TEXT NOT NULL,
                outcome TEXT NOT NULL,
                provenance TEXT NOT NULL,
                trust_tier TEXT NOT NULL,
                supersession TEXT NOT NULL DEFAULT 'active',
                source_run_id TEXT DEFAULT '',
                use_count INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_used DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


async def store_pattern(
    db_path: str,
    *,
    situation_shape: Mapping[str, Any] | None,
    method: Any,
    outcome: Any = "succeeded",
    provenance: Any = "untrusted_touched",
    supersession: str = "active",
    source_run_id: str = "",
) -> str | None:
    await init_pattern_db(db_path)
    shape = normalize_situation_shape(situation_shape)
    steps = normalize_method(method)
    if not steps:
        return None
    normalized_provenance = normalize_provenance(provenance)
    normalized_supersession = supersession if supersession in SUPERSESSION_VALUES else "active"
    pattern_id = f"pat_{uuid.uuid4().hex[:12]}"
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO harness_patterns (
                pattern_id, task_category, source_type, goal_type, method_json,
                outcome, provenance, trust_tier, supersession, source_run_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pattern_id,
                shape["task_category"],
                shape["source_type"],
                shape["goal_type"],
                json.dumps(list(steps)),
                normalize_outcome(outcome),
                normalized_provenance,
                trust_tier_for(normalized_provenance),
                normalized_supersession,
                str(source_run_id or ""),
            ),
        )
        await db.commit()
    return pattern_id


async def retrieve_pattern_facts(db_path: str, state: Mapping[str, Any], limit: int = MAX_RETRIEVED_PATTERNS) -> list[dict[str, Any]]:
    await init_pattern_db(db_path)
    shape = derive_situation_shape(state)
    limit = max(0, min(int(limit), MAX_RETRIEVED_PATTERNS))
    if not limit:
        return []
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT *
            FROM harness_patterns
            WHERE supersession = 'active'
              AND task_category = ?
              AND source_type = ?
              AND goal_type = ?
            ORDER BY
              CASE trust_tier WHEN 'method_safe' THEN 0 ELSE 1 END,
              CASE outcome WHEN 'succeeded' THEN 0 ELSE 1 END,
              use_count DESC,
              last_used DESC
            LIMIT ?
            """,
            (shape["task_category"], shape["source_type"], shape["goal_type"], limit),
        )
        rows = await cursor.fetchall()
        ids = [str(row["pattern_id"]) for row in rows]
        if ids:
            placeholders = ",".join("?" for _ in ids)
            await db.execute(
                f"""
                UPDATE harness_patterns
                SET use_count = use_count + 1, last_used = CURRENT_TIMESTAMP
                WHERE pattern_id IN ({placeholders})
                """,
                ids,
            )
            await db.commit()
    return [pattern_fact_from_row(dict(row)) for row in rows]


async def record_pattern_from_episode(db_path: str, state: Mapping[str, Any]) -> str | None:
    if not state.get("agentic_loop"):
        return None
    return await store_pattern(
        db_path,
        situation_shape=derive_situation_shape(state),
        method=derive_method(state),
        outcome=derive_outcome(state),
        provenance=derive_episode_provenance(state),
        source_run_id=str(state.get("run_id") or ""),
    )


async def mark_pattern_supersession(db_path: str, pattern_id: str, supersession: str) -> None:
    if supersession not in SUPERSESSION_VALUES:
        return
    await init_pattern_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE harness_patterns SET supersession = ? WHERE pattern_id = ?",
            (supersession, pattern_id),
        )
        await db.commit()


async def list_patterns(db_path: str) -> list[dict[str, Any]]:
    await init_pattern_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM harness_patterns ORDER BY created_at, pattern_id")
        rows = await cursor.fetchall()
    records: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["method"] = json.loads(str(item.pop("method_json") or "[]"))
        records.append(item)
    return records
