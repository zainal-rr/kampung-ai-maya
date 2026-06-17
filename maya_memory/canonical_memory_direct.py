from __future__ import annotations

import aiosqlite

from maya_memory.canonical_memory_embeddings import EmbedCall
from maya_memory.canonical_memory_fts import fts_rank_bonuses
from maya_memory.canonical_memory_scoring import activation_score
from maya_memory.canonical_memory_semantic import semantic_direct_recall_candidates
from maya_memory.canonical_memory_text import memory_tokens, subject_key_from_text
from maya_memory.canonical_memory_usage import mark_canonical_used


async def search_canonical_direct_fact_impl(
    db_path: str,
    query: str,
    limit: int = 3,
    *,
    embedding_agent: EmbedCall | None = None,
) -> list[str] | None:
    subject_key = subject_key_from_text(query)
    if not subject_key:
        return []
    query_tokens = memory_tokens(subject_key)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        fts_bonuses = await fts_rank_bonuses(db, query)
        active = await db.execute(
            """
            SELECT memory_id, subject_key, content, pinned, temporary, updated_at,
                   COALESCE(reinforcement_count, 0) AS reinforcement_count
            FROM canonical_memory_items
            WHERE status = 'active'
              AND (expires_at IS NULL OR expires_at > datetime('now'))
            ORDER BY updated_at DESC
            """
        )
        active_rows = await active.fetchall()
        rows = [row for row in active_rows if _direct_fact_match(query_tokens, subject_key, row["subject_key"], row["content"])][:limit]
        if not rows and await _tombstone_matches(db, query_tokens, subject_key):
            return None
    if not rows:
        candidates = _semantic_direct_candidate_pool(active_rows, query_tokens, fts_bonuses)
        semantic_rows = await semantic_direct_recall_candidates(
            db_path,
            query,
            candidates,
            embedding_agent=embedding_agent,
        )
        selected = [(memory_id, content) for _score, memory_id, content in semantic_rows[:limit]]
    else:
        selected = [(str(row["memory_id"]), str(row["content"])) for row in rows[:limit]]
    await mark_canonical_used(
        db_path,
        [memory_id for memory_id, _content in selected],
        event_type="canonical_recall",
        source_ref=query,
    )
    return [content for _memory_id, content in selected]


def _direct_fact_match(query_tokens: set[str], subject_key: str, row_subject: str, row_content: str) -> bool:
    return row_subject == subject_key or (
        len(query_tokens) >= 2 and query_tokens.issubset(memory_tokens(f"{row_subject} {row_content}"))
    )


async def _tombstone_matches(db: aiosqlite.Connection, query_tokens: set[str], subject_key: str) -> bool:
    forgotten = await db.execute(
        """
        SELECT subject_key, content FROM canonical_memory_items
        WHERE status IN ('forgotten', 'expired', 'superseded')
        ORDER BY updated_at DESC
        """
    )
    return any(
        _direct_fact_match(query_tokens, subject_key, row["subject_key"], row["content"])
        for row in await forgotten.fetchall()
    )


def _semantic_direct_candidate_pool(
    rows: list[aiosqlite.Row],
    query_tokens: set[str],
    fts_bonuses: dict[str, int],
) -> list[tuple[int, str, str]]:
    scored = []
    for row in rows:
        memory_id = str(row["memory_id"])
        haystack = f"{row['subject_key']} {row['content']}"
        overlap = len(query_tokens & memory_tokens(haystack))
        fts_bonus = fts_bonuses.get(memory_id, 0)
        if row["temporary"] and overlap == 0 and not fts_bonus:
            continue
        score = activation_score(
            overlap=overlap,
            pinned=bool(row["pinned"]),
            reinforcement_count=int(row["reinforcement_count"]),
            updated_at=str(row["updated_at"] or ""),
        ) + fts_bonus
        scored.append((score, memory_id, str(row["content"])))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[:64]
