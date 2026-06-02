from __future__ import annotations

from dataclasses import dataclass

import aiosqlite

from canonical_memory import (
    _internal_memory,
    _memory_id,
    init_canonical_memory_db,
    subject_key_from_text,
    upsert_canonical_memory,
)


@dataclass(frozen=True)
class CanonicalMigrationReport:
    preferences_seen: int = 0
    lessons_seen: int = 0
    sources_linked: int = 0
    canonical_created: int = 0
    canonical_updated: int = 0
    duplicates: int = 0
    skipped_internal: int = 0

    def text(self) -> str:
        return "\n".join((
            "Canonical memory migration:",
            f"1) Preferences scanned: {self.preferences_seen}",
            f"2) Lessons scanned: {self.lessons_seen}",
            f"3) Source rows linked: {self.sources_linked}",
            f"4) Canonical records created: {self.canonical_created}",
            f"5) Canonical records updated: {self.canonical_updated}",
            f"6) Duplicate source links: {self.duplicates}",
            f"7) Internal rows skipped: {self.skipped_internal}",
        ))


async def migrate_memory_to_canonical(db_path: str) -> str:
    return (await migrate_canonical_memory(db_path)).text()


async def migrate_canonical_memory(db_path: str) -> CanonicalMigrationReport:
    await init_canonical_memory_db(db_path)
    await _init_migration_db(db_path)
    pref_rows, lesson_rows = await _legacy_memory_rows(db_path)
    linked = created = updated = duplicates = skipped = 0
    for row in pref_rows:
        key = str(row["key"])
        value = str(row["value"])
        if _internal_memory(key, value):
            skipped += 1
            continue
        result = await _migrate_source(
            db_path,
            source_table="preferences",
            source_id=key,
            content=value,
            raw_text=key,
            kind="preference",
            scope="global",
            source_channel=str(row["source"]),
            confidence="high",
        )
        linked += result["linked"]
        created += result["created"]
        updated += result["updated"]
        duplicates += result["duplicate"]
    for row in lesson_rows:
        result = await _migrate_source(
            db_path,
            source_table="lessons",
            source_id=str(row["id"]),
            content=str(row["normalized_rule"]),
            raw_text=str(row["normalized_rule"]),
            kind=str(row["lesson_type"] or "lesson"),
            scope=str(row["scope"] or "global"),
            source_channel=str(row["channel"]),
            confidence=str(row["confidence"] or "medium"),
        )
        linked += result["linked"]
        created += result["created"]
        updated += result["updated"]
        duplicates += result["duplicate"]
    return CanonicalMigrationReport(len(pref_rows), len(lesson_rows), linked, created, updated, duplicates, skipped)


async def _init_migration_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS canonical_memory_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id TEXT NOT NULL,
                source_table TEXT NOT NULL,
                source_id TEXT NOT NULL,
                source_channel TEXT DEFAULT '',
                linked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source_table, source_id)
            )
            """
        )
        await db.commit()


async def _legacy_memory_rows(db_path: str) -> tuple[list[aiosqlite.Row], list[aiosqlite.Row]]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        pref_rows = await (await db.execute("SELECT key, value, source FROM preferences")).fetchall()
        try:
            lesson_rows = await (
                await db.execute("SELECT id, normalized_rule, lesson_type, scope, channel, confidence FROM lessons WHERE status = 'active'")
            ).fetchall()
        except aiosqlite.OperationalError:
            lesson_rows = []
    return pref_rows, lesson_rows


async def _migrate_source(
    db_path: str,
    *,
    source_table: str,
    source_id: str,
    content: str,
    raw_text: str,
    kind: str,
    scope: str,
    source_channel: str,
    confidence: str,
) -> dict[str, int]:
    memory_id = _memory_id(kind, subject_key_from_text(content), scope)
    existed = await _canonical_exists(db_path, memory_id)
    await upsert_canonical_memory(
        db_path,
        raw_text=raw_text,
        content=content,
        kind=kind,
        scope=scope,
        source_channel=source_channel,
        confidence=confidence,
        source_ref=f"{source_table}:{source_id}",
    )
    linked = await _link_source(db_path, memory_id, source_table, source_id, source_channel)
    return {"linked": linked, "created": 0 if existed else 1, "updated": 1 if existed else 0, "duplicate": 0 if linked else 1}


async def _canonical_exists(db_path: str, memory_id: str) -> bool:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT 1 FROM canonical_memory_items WHERE memory_id = ? LIMIT 1", (memory_id,))
        return await cursor.fetchone() is not None


async def _link_source(db_path: str, memory_id: str, source_table: str, source_id: str, source_channel: str) -> int:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            INSERT OR IGNORE INTO canonical_memory_sources (memory_id, source_table, source_id, source_channel)
            VALUES (?, ?, ?, ?)
            """,
            (memory_id, source_table, source_id, source_channel),
        )
        await db.commit()
        return 1 if cursor.rowcount else 0
