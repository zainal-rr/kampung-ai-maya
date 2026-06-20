from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import aiosqlite


@dataclass(frozen=True)
class ArtifactFingerprint:
    path: str
    sha256: str
    mtime_ns: int
    size: int


async def init_artifact_file_state_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS artifact_file_state (
                path TEXT PRIMARY KEY,
                sha256 TEXT NOT NULL,
                mtime_ns INTEGER NOT NULL,
                size INTEGER NOT NULL,
                source TEXT NOT NULL DEFAULT 'maya',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


async def record_artifact_fingerprint(db_path: str, path: Path, *, source: str = "maya") -> ArtifactFingerprint | None:
    if not path.exists() or not path.is_file():
        return None
    fingerprint = await artifact_fingerprint(path)
    await init_artifact_file_state_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO artifact_file_state (path, sha256, mtime_ns, size, source, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(path) DO UPDATE SET
                sha256 = excluded.sha256,
                mtime_ns = excluded.mtime_ns,
                size = excluded.size,
                source = excluded.source,
                updated_at = CURRENT_TIMESTAMP
            """,
            (fingerprint.path, fingerprint.sha256, fingerprint.mtime_ns, fingerprint.size, source),
        )
        await db.commit()
    return fingerprint


async def artifact_changed_since_recorded(db_path: str, path: Path) -> bool:
    if not path.exists() or not path.is_file():
        return True
    await init_artifact_file_state_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT sha256, mtime_ns, size FROM artifact_file_state WHERE path = ?",
            (str(path),),
        )
        row = await cursor.fetchone()
    if not row:
        # Legacy artifacts and smoke fixtures created before the fingerprint
        # layer should keep the old edit behavior. New Maya-created artifacts
        # are recorded through DocumentActionRouter._remember and get the full
        # manual-edit safety check.
        return False
    current = await artifact_fingerprint(path)
    return (
        current.sha256 != str(row["sha256"])
        or current.mtime_ns != int(row["mtime_ns"] or 0)
        or current.size != int(row["size"] or 0)
    )


async def artifact_fingerprint(path: Path) -> ArtifactFingerprint:
    stat = path.stat()
    return ArtifactFingerprint(
        path=str(path),
        sha256=_sha256(path),
        mtime_ns=int(stat.st_mtime_ns),
        size=int(stat.st_size),
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
