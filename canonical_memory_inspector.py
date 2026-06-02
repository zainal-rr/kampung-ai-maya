from __future__ import annotations

import aiosqlite

from canonical_memory import init_canonical_memory_db, memory_tokens, subject_key_from_text


async def inspect_canonical_memory(db_path: str, query: str = "", limit: int = 8) -> str:
    cleaned = " ".join(query.strip().split())
    rows = await _inspection_rows(db_path, cleaned, limit)
    if not rows:
        suffix = f" matching: {cleaned}" if cleaned else ""
        return f"Canonical memory inspector:\n1) No canonical memory found{suffix}."
    lines = ["Canonical memory inspector:"]
    for idx, row in enumerate(rows, start=1):
        lines.append(
            "\n".join((
                f"{idx}) id: {row['memory_id']}",
                f"   class: {_activation_class(row)}",
                f"   subject: {row['subject_key']}",
                f"   kind/status: {row['kind']} / {row['status']}",
                f"   flags: pinned={bool(row['pinned'])}, temporary={bool(row['temporary'])}, test={bool(row['test_marker'])}",
                f"   reinforcement: {int(row['reinforcement_count'] or 0)}",
                f"   updated: {row['updated_at']}; last used: {row['last_used_at'] or 'never'}",
                f"   content: {_preview(row['content'])}",
            ))
        )
    return "\n".join(lines)


async def _inspection_rows(db_path: str, query: str, limit: int) -> list[aiosqlite.Row]:
    await init_canonical_memory_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        rows = await (
            await db.execute(
                """
                SELECT memory_id, kind, subject_key, content, status, pinned, temporary,
                       test_marker, updated_at, last_used_at,
                       COALESCE(reinforcement_count, 0) AS reinforcement_count
                FROM canonical_memory_items
                ORDER BY pinned DESC, updated_at DESC
                LIMIT 160
                """
            )
        ).fetchall()
    return _filter_rows(rows, query)[:limit]


def _filter_rows(rows: list[aiosqlite.Row], query: str) -> list[aiosqlite.Row]:
    if not query:
        return rows
    subject_key = subject_key_from_text(query)
    tokens = memory_tokens(query)
    filtered = []
    for row in rows:
        haystack = f"{row['memory_id']} {row['subject_key']} {row['content']}"
        if query == row["memory_id"] or (subject_key and subject_key == row["subject_key"]):
            filtered.append(row)
        elif tokens and tokens.issubset(memory_tokens(haystack)):
            filtered.append(row)
    return filtered


def _activation_class(row: aiosqlite.Row) -> str:
    status = str(row["status"])
    if status in {"forgotten", "expired", "superseded"}:
        return status
    if row["pinned"]:
        return "pinned"
    if row["temporary"] or row["test_marker"]:
        return "temporary_test"
    return "active_saved_fact"


def _preview(value: str, limit: int = 120) -> str:
    cleaned = " ".join(str(value).split())
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 3] + "..."
