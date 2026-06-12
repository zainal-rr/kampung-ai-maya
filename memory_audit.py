from __future__ import annotations

import hashlib
from dataclasses import dataclass

import aiosqlite

from permission_policy import contains_sensitive_info

AUDIT_EVENT_TYPES = {
    "canonical_write",
    "canonical_update",
    "canonical_forget",
    "canonical_recall",
    "canonical_supersede",
    "canonical_write_blocked_forgotten",
    "weekly_candidate",
    "weekly_save",
    "weekly_reject",
    "activation",
    "leak_check",
    "extraction_divergence",
}


@dataclass(frozen=True)
class MemoryAuditEvent:
    event_type: str
    memory_id: str
    subject_key: str
    status_before: str
    status_after: str
    source_channel: str
    source_ref: str
    run_id: str
    thread_id: str
    content_hash: str
    content_preview: str
    created_at: str


async def init_memory_audit_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                memory_id TEXT DEFAULT '',
                subject_key TEXT DEFAULT '',
                status_before TEXT DEFAULT '',
                status_after TEXT DEFAULT '',
                source_channel TEXT DEFAULT '',
                source_ref TEXT DEFAULT '',
                run_id TEXT DEFAULT '',
                thread_id TEXT DEFAULT '',
                content_hash TEXT DEFAULT '',
                content_preview TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memory_audit_subject_time
            ON memory_audit_events(subject_key, created_at)
            """
        )
        await db.commit()


async def record_memory_audit_event(
    db_path: str,
    *,
    event_type: str,
    memory_id: str = "",
    subject_key: str = "",
    status_before: str = "",
    status_after: str = "",
    source_channel: str = "",
    source_ref: str = "",
    run_id: str = "",
    thread_id: str = "",
    content: str = "",
) -> None:
    if event_type not in AUDIT_EVENT_TYPES:
        raise ValueError(f"Unknown memory audit event type: {event_type}")
    await init_memory_audit_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO memory_audit_events (
                event_type, memory_id, subject_key, status_before, status_after,
                source_channel, source_ref, run_id, thread_id, content_hash,
                content_preview
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_type,
                memory_id,
                subject_key,
                status_before,
                status_after,
                source_channel,
                source_ref[:240],
                run_id,
                thread_id,
                hash_content(content),
                redacted_preview(content),
            ),
        )
        await db.commit()


async def recent_memory_audit_events(
    db_path: str,
    *,
    query: str = "",
    limit: int = 8,
) -> list[MemoryAuditEvent]:
    await init_memory_audit_db(db_path)
    where = ""
    params: tuple[str | int, ...]
    if query:
        pattern = f"%{query}%"
        where = "WHERE subject_key LIKE ? OR memory_id LIKE ? OR content_preview LIKE ?"
        params = (pattern, pattern, pattern, limit)
    else:
        params = (limit,)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""
            SELECT event_type, memory_id, subject_key, status_before, status_after,
                   source_channel, source_ref, run_id, thread_id, content_hash,
                   content_preview, created_at
            FROM memory_audit_events
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            params,
        )
        rows = await cursor.fetchall()
    return [MemoryAuditEvent(**dict(row)) for row in rows]


async def format_recent_memory_audit(db_path: str, query: str = "", limit: int = 6) -> str:
    events = await recent_memory_audit_events(db_path, query=query, limit=limit)
    if not events:
        return "Recent memory audit:\n1) No memory audit events recorded yet."
    lines = ["Recent memory audit:"]
    for index, event in enumerate(events, start=1):
        status = _status_change(event)
        lines.append(
            f"{index}) {event.created_at} | {event.event_type} | {event.subject_key or event.memory_id or 'n/a'} | {status} | {event.content_preview}"
        )
    return "\n".join(lines)


def hash_content(content: str) -> str:
    if not content:
        return ""
    return hashlib.sha256(str(content).encode("utf-8")).hexdigest()


def redacted_preview(content: str, limit: int = 120) -> str:
    cleaned = " ".join(str(content).split())
    if not cleaned:
        return ""
    if contains_sensitive_info(cleaned):
        return "[redacted-sensitive]"
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 3] + "..."


def _status_change(event: MemoryAuditEvent) -> str:
    if event.status_before or event.status_after:
        return f"{event.status_before or '?'}->{event.status_after or '?'}"
    return "-"
