from __future__ import annotations

import aiosqlite

from skill_store import create_skill_proposal
from skill_memory_store import add_skill_memory


OUTCOMES = {"success", "failure", "partial", "user_corrected", "blocked", "cancelled"}


async def init_skill_outcome_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS skill_outcome_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_id TEXT NOT NULL,
                user_request TEXT NOT NULL,
                channel TEXT DEFAULT '',
                selected_lane TEXT DEFAULT '',
                reason_selected TEXT DEFAULT '',
                outcome TEXT NOT NULL,
                missing_step TEXT DEFAULT '',
                user_correction TEXT DEFAULT '',
                artifact_or_workflow_id TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


async def record_skill_outcome(
    db_path: str,
    *,
    skill_id: str,
    user_request: str,
    outcome: str,
    channel: str = "",
    selected_lane: str = "",
    reason_selected: str = "",
    missing_step: str = "",
    user_correction: str = "",
    artifact_or_workflow_id: str = "",
) -> None:
    await init_skill_outcome_db(db_path)
    clean_outcome = outcome if outcome in OUTCOMES else "partial"
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO skill_outcome_events (
                skill_id, user_request, channel, selected_lane, reason_selected,
                outcome, missing_step, user_correction, artifact_or_workflow_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                skill_id,
                user_request[:800],
                channel,
                selected_lane,
                reason_selected[:300],
                clean_outcome,
                missing_step[:500],
                user_correction[:500],
                artifact_or_workflow_id[:120],
            ),
        )
        await db.commit()
    if clean_outcome == "success" and await _outcome_count(db_path, skill_id, "success") >= 2:
        await add_skill_memory(
            db_path,
            skill_id=skill_id,
            kind="example",
            content=user_request,
            source="repeated_success",
            confidence=0.7,
        )
    if clean_outcome == "failure" and await _outcome_count(db_path, skill_id, "failure") >= 2:
        await create_skill_proposal(
            db_path,
            skill_id,
            f"Improve skill {skill_id}",
            f"Improve {skill_id} after repeated failures.",
            missing_step or "Review recent failed outcomes before changing active behavior.",
        )


async def recent_skill_outcomes(db_path: str, limit: int = 12) -> list[dict[str, str]]:
    await init_skill_outcome_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT skill_id, user_request, channel, selected_lane, reason_selected,
                   outcome, missing_step, user_correction, artifact_or_workflow_id, created_at
            FROM skill_outcome_events
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def skill_outcome_counts(db_path: str, skill_id: str | None = None) -> dict[str, int]:
    await init_skill_outcome_db(db_path)
    query = "SELECT outcome, COUNT(*) FROM skill_outcome_events GROUP BY outcome"
    params: tuple[str, ...] = ()
    if skill_id:
        query = "SELECT outcome, COUNT(*) FROM skill_outcome_events WHERE skill_id = ? GROUP BY outcome"
        params = (skill_id,)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
    return {str(outcome): int(count) for outcome, count in rows}


async def repeated_failure_skills(db_path: str, threshold: int = 2) -> list[str]:
    await init_skill_outcome_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            SELECT skill_id
            FROM skill_outcome_events
            WHERE outcome = 'failure'
            GROUP BY skill_id
            HAVING COUNT(*) >= ?
            """,
            (threshold,),
        )
        rows = await cursor.fetchall()
    return [str(row[0]) for row in rows]


async def _outcome_count(db_path: str, skill_id: str, outcome: str) -> int:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM skill_outcome_events WHERE skill_id = ? AND outcome = ?",
            (skill_id, outcome),
        )
        row = await cursor.fetchone()
    return int(row[0] if row else 0)


async def propose_improvements_for_repeated_failures(db_path: str, threshold: int = 2) -> list[str]:
    proposed = []
    for skill_id in await repeated_failure_skills(db_path, threshold):
        proposal_id = await create_skill_proposal(
            db_path,
            skill_id,
            f"Improve skill {skill_id}",
            f"Improve {skill_id} after repeated failures.",
            "Review failure outcomes and update triggers, tools, safety, or tests before activation.",
        )
        proposed.append(str(proposal_id))
    return proposed
