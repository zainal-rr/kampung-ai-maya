from __future__ import annotations

import aiosqlite

from harness_models import HarnessArtifact
from harness_store import init_harness_db


async def init_harness_artifact_db(db_path: str) -> None:
    await init_harness_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        for statement in (
            "ALTER TABLE harness_artifacts ADD COLUMN url TEXT DEFAULT ''",
            "ALTER TABLE harness_artifacts ADD COLUMN source_tool TEXT DEFAULT ''",
            "ALTER TABLE harness_artifacts ADD COLUMN exists_status TEXT DEFAULT 'unknown'",
            "ALTER TABLE harness_artifacts ADD COLUMN delivery_status TEXT DEFAULT 'local'",
            "ALTER TABLE harness_artifacts ADD COLUMN checksum TEXT DEFAULT ''",
        ):
            try:
                await db.execute(statement)
            except aiosqlite.OperationalError:
                pass
        await db.commit()


async def record_structured_artifact(db_path: str, run_id: str, artifact: HarnessArtifact) -> None:
    await init_harness_artifact_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            SELECT 1 FROM harness_artifacts
            WHERE run_id = ? AND kind = ? AND path = ? AND url = ?
            LIMIT 1
            """,
            (run_id, artifact.kind, artifact.path, artifact.url),
        )
        if await cursor.fetchone():
            return
        await db.execute(
            """
            INSERT INTO harness_artifacts (
                run_id, kind, path, url, summary, source_tool,
                exists_status, delivery_status, checksum
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                artifact.kind,
                artifact.path,
                artifact.url,
                artifact.summary[:500],
                artifact.source_tool,
                artifact.exists_status,
                artifact.delivery_status,
                artifact.checksum,
            ),
        )
        await db.commit()


async def latest_artifacts(db_path: str, run_id: str | None = None, limit: int = 5) -> list[dict[str, str]]:
    await init_harness_artifact_db(db_path)
    where = "WHERE run_id = ?" if run_id else ""
    params: tuple[str | int, ...] = (run_id, limit) if run_id else (limit,)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""
            SELECT id, run_id, kind, path, url, summary, source_tool,
                   exists_status, delivery_status, checksum, created_at
            FROM harness_artifacts
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            params,
        )
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]
