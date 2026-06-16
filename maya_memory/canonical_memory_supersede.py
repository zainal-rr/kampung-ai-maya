"""W2-A — supersede instead of overwrite (deterministic memory honesty).

Spec: docs/blast_radius_and_retrieval_design_2026-06-12.md (W2-A).
Canaries: memory_supersede_canaries_smoke.py (R1-R3).

When a fact's value changes, the prior canonical row is archived with status
'superseded' (a terminal state DISTINCT from 'forgotten') before the active
row is updated in place. The active row keeps its stable memory_id, so links,
vectors, and usage references never ripple. History stays retrievable on
demand; forget still tombstones the WHOLE chain (R3).
"""

from __future__ import annotations

import aiosqlite

from maya_memory.canonical_memory_text import memory_tokens, subject_key_from_text
from memory_audit import record_memory_audit_event

SUPERSEDED_STATUS = "superseded"


async def load_existing_for_upsert(
    db: aiosqlite.Connection,
    kind: str,
    subject_key: str,
    scope: str,
    memory_id: str,
):
    """Return (active_row, effective_status) for an upsert. If no active row
    exists, fall back to the latest tombstone status so a forgotten fact still
    blocks resurrection by derived writers."""
    active = await (
        await db.execute(
            """
            SELECT memory_id, kind, subject_key, content, value, scope,
                   source_channel, source_ref, confidence, status,
                   created_at, updated_at, pinned, temporary, test_marker
            FROM canonical_memory_items
            WHERE kind = ? AND subject_key = ? AND scope = ? AND status = 'active'
            """,
            (kind, subject_key, scope),
        )
    ).fetchone()
    if active:
        return active, str(active["status"])
    base_tombstone = await (
        await db.execute(
            """
            SELECT memory_id, kind, subject_key, content, value, scope,
                   source_channel, source_ref, confidence, status,
                   created_at, updated_at, pinned, temporary, test_marker
            FROM canonical_memory_items
            WHERE memory_id = ? AND status IN ('forgotten', 'expired')
            """,
            (memory_id,),
        )
    ).fetchone()
    if base_tombstone:
        return base_tombstone, str(base_tombstone["status"])
    tomb = await (
        await db.execute(
            """
            SELECT status FROM canonical_memory_items
            WHERE kind = ? AND subject_key = ? AND scope = ?
            ORDER BY updated_at DESC LIMIT 1
            """,
            (kind, subject_key, scope),
        )
    ).fetchone()
    return None, (str(tomb["status"]) if tomb else "")


async def write_active_memory_row(
    db: aiosqlite.Connection,
    *,
    memory_id: str,
    kind: str,
    subject_key: str,
    content: str,
    value: str,
    scope: str,
    source_channel: str,
    source_ref: str,
    confidence: str,
    expires_at: str | None,
    pinned: bool,
    temporary: bool,
    existing_status: str,
) -> None:
    """Write the active truth row. Forgotten/expired base rows are reactivated
    in place so explicit user re-saves keep the stable memory_id."""
    payload = (
        content,
        value,
        source_channel,
        source_ref,
        confidence,
        expires_at,
        int(pinned),
        int(temporary),
        int(temporary),
    )
    if existing_status in {"forgotten", "expired"}:
        await db.execute(
            """
            UPDATE canonical_memory_items
            SET content = ?, value = ?, source_channel = ?, source_ref = ?,
                confidence = ?, status = 'active', expires_at = ?,
                pinned = MAX(pinned, ?), temporary = ?, test_marker = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE memory_id = ?
            """,
            (*payload, memory_id),
        )
        return
    await db.execute(
        """
        INSERT INTO canonical_memory_items (
            memory_id, kind, subject_key, content, value, scope,
            source_channel, source_ref, confidence, status, expires_at,
            pinned, temporary, test_marker, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(kind, subject_key, scope) WHERE status = 'active' DO UPDATE SET
            content = excluded.content,
            value = excluded.value,
            source_channel = excluded.source_channel,
            source_ref = excluded.source_ref,
            confidence = excluded.confidence,
            status = 'active',
            expires_at = excluded.expires_at,
            pinned = MAX(pinned, excluded.pinned),
            temporary = excluded.temporary,
            test_marker = excluded.test_marker,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            memory_id,
            kind,
            subject_key,
            content,
            value,
            scope,
            source_channel,
            source_ref,
            confidence,
            expires_at,
            int(pinned),
            int(temporary),
            int(temporary),
        ),
    )


async def record_supersede_audit(
    db_path: str,
    *,
    archive_id: str,
    subject_key: str,
    prev_content: str,
    source_channel: str,
    source_ref: str,
) -> None:
    """Append-only evidence that a value was archived (W2-A). Called AFTER the
    upsert commits so it never contends for the write lock."""
    await record_memory_audit_event(
        db_path,
        event_type="canonical_supersede",
        memory_id=archive_id,
        subject_key=subject_key,
        status_before="active",
        status_after=SUPERSEDED_STATUS,
        source_channel=source_channel,
        source_ref=source_ref,
        content=prev_content,
    )


async def ensure_supersede_schema(db: aiosqlite.Connection) -> None:
    """Additive migration: chain columns + the truth index becomes PARTIAL
    (unique active row per (kind, subject_key, scope); archive rows may share
    the triple). Safe to run on every init."""
    for ddl in (
        "ALTER TABLE canonical_memory_items ADD COLUMN superseded_by TEXT DEFAULT ''",
        "ALTER TABLE canonical_memory_items ADD COLUMN superseded_at DATETIME",
    ):
        try:
            await db.execute(ddl)
        except aiosqlite.OperationalError:
            pass
    await db.execute("DROP INDEX IF EXISTS idx_canonical_memory_truth")
    await db.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_canonical_memory_truth_active
        ON canonical_memory_items(kind, subject_key, scope)
        WHERE status = 'active'
        """
    )


def should_supersede(existing_row, new_content: str) -> bool:
    """Archive only real value changes on durable facts: active, non-temporary,
    and the content actually differs. Re-saves of the same content reinforce in
    place; temporary test memories never grow history."""
    if existing_row is None:
        return False
    if str(existing_row["status"]) != "active":
        return False
    if int(existing_row["temporary"] or 0):
        return False
    return str(existing_row["content"]).strip() != new_content.strip()


async def archive_superseded_value(
    db: aiosqlite.Connection,
    existing_row,
    *,
    active_memory_id: str,
) -> str:
    """Copy the outgoing active row into a 'superseded' archive row with its
    own memory_id, using the caller's open transaction (no commit, no second
    connection — the audit event is recorded by the caller AFTER commit, the
    same pattern as canonical_write/canonical_update). Returns the archive id."""
    count_row = await (
        await db.execute(
            "SELECT COUNT(*) AS n FROM canonical_memory_items WHERE superseded_by = ?",
            (active_memory_id,),
        )
    ).fetchone()
    archive_id = f"{active_memory_id}_s{int(count_row['n']) + 1}"
    await db.execute(
        """
        INSERT OR IGNORE INTO canonical_memory_items (
            memory_id, kind, subject_key, content, value, scope,
            source_channel, source_ref, confidence, status,
            created_at, updated_at, pinned, temporary, test_marker,
            superseded_by, superseded_at
        )
        SELECT ?, kind, subject_key, content, value, scope,
               source_channel, source_ref, confidence, ?,
               created_at, CURRENT_TIMESTAMP, 0, temporary, test_marker,
               ?, CURRENT_TIMESTAMP
        FROM canonical_memory_items
        WHERE memory_id = ?
        """,
        (archive_id, SUPERSEDED_STATUS, active_memory_id, active_memory_id),
    )
    return archive_id


async def canonical_memory_history(
    db_path: str, query: str, limit: int = 10
) -> list[dict[str, str]]:
    """Current value plus its superseded chain, newest first. Forgotten rows
    are NEVER part of history (R2/R3): supersede keeps history, forget removes
    it across all tiers."""
    subject_key = subject_key_from_text(query)
    tokens = memory_tokens(subject_key or query)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT subject_key, content, status, updated_at, superseded_at
            FROM canonical_memory_items
            WHERE status IN ('active', 'superseded')
            ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, updated_at DESC
            """
        )
        rows = await cursor.fetchall()
    matches: list[dict[str, str]] = []
    for row in rows:
        haystack = f"{row['subject_key']} {row['content']}"
        if (subject_key and row["subject_key"] == subject_key) or (
            tokens and len(tokens) >= 2 and tokens.issubset(memory_tokens(haystack))
        ):
            matches.append(
                {
                    "content": str(row["content"]),
                    "status": str(row["status"]),
                    "as_of": str(row["superseded_at"] or row["updated_at"] or ""),
                }
            )
        if len(matches) >= limit:
            break
    return matches
