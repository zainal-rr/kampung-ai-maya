from __future__ import annotations

import json

import aiosqlite

from maya_harness.harness_models import GroundedObservation
from maya_harness.harness_store import init_harness_db


async def init_harness_observation_db(db_path: str) -> None:
    await init_harness_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS harness_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                source TEXT DEFAULT '',
                observation_json TEXT DEFAULT '{}',
                confidence REAL DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


async def record_observation(db_path: str, run_id: str, observation: GroundedObservation) -> None:
    await init_harness_observation_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO harness_observations (run_id, source, observation_json, confidence)
            VALUES (?, ?, ?, ?)
            """,
            (run_id, observation.source, json.dumps(observation.as_dict()), observation.confidence),
        )
        await db.commit()


async def latest_observation(db_path: str, run_id: str | None = None) -> dict | None:
    await init_harness_observation_db(db_path)
    where = "WHERE run_id = ?" if run_id else ""
    params: tuple[str, ...] = (run_id,) if run_id else ()
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""
            SELECT *
            FROM harness_observations
            {where}
            ORDER BY id DESC
            LIMIT 1
            """,
            params,
        )
        row = await cursor.fetchone()
    if not row:
        return None
    data = dict(row)
    data["observation"] = json.loads(data.pop("observation_json") or "{}")
    return data
