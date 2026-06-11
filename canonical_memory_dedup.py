from __future__ import annotations

"""Semantic duplicate detection for canonical memory writers.

Why this exists: the canonical truth key (kind, subject_key, scope) only
deduplicates identical subject keys. Derived writers (nightly consolidation)
phrase facts as full sentences, so subject_key_from_text mints a new key for
every rephrasing and the truth-key dedup never fires. Night after night this
accretes paraphrases of the same preference. This gate catches duplicates by
meaning before they are inserted.

Two layers, cheapest first:
1. Token containment (no key needed): if nearly all of the candidate's
   informative tokens already appear in one active row (and vice versa
   enough), it is a rephrasing. Threshold is strict (0.8) because a false
   positive here silently drops a NEW fact, which is worse than keeping a
   duplicate.
2. Embedding cosine (optional, fail-open): catches cross-phrasing duplicates
   tokens cannot, e.g. "never uses dash symbols in any responses" vs
   "Do not use dash symbols in replies". Only runs when an embed agent is
   supplied; any provider error falls back to the token verdict.
"""

import aiosqlite

from canonical_memory_embeddings import EmbedCall, _cosine
from canonical_memory_text import memory_tokens

TOKEN_CONTAINMENT_THRESHOLD = 0.8
EMBED_DUPLICATE_COSINE = 0.86
MAX_CANDIDATE_ROWS = 24
MIN_TOKENS = 3


async def find_semantic_duplicate(
    db_path: str,
    content: str,
    *,
    embed_agent: EmbedCall | None = None,
) -> tuple[str, str] | None:
    """Return (memory_id, reason) of an active row that duplicates `content`.

    reason is "token_containment" or "embedding_cosine". Returns None when no
    confident duplicate exists; uncertain cases are NOT duplicates by design.
    """
    tokens = memory_tokens(content)
    if len(tokens) < MIN_TOKENS:
        return None
    candidates = await _candidate_rows(db_path, tokens)
    if not candidates:
        return None
    for memory_id, row_text in candidates:
        row_tokens = memory_tokens(row_text)
        if not row_tokens:
            continue
        shared = tokens & row_tokens
        containment = len(shared) / len(tokens)
        reverse = len(shared) / len(row_tokens)
        if containment >= TOKEN_CONTAINMENT_THRESHOLD and reverse >= 0.5:
            return memory_id, "token_containment"
    if embed_agent is None:
        return None
    try:
        texts = [content] + [row_text for _mid, row_text in candidates]
        vectors = await embed_agent(texts)
    except Exception:
        return None
    if len(vectors) != len(texts):
        return None
    content_vector = vectors[0]
    best: tuple[float, str] | None = None
    for (memory_id, _row_text), vector in zip(candidates, vectors[1:]):
        cosine = _cosine(content_vector, vector)
        if cosine >= EMBED_DUPLICATE_COSINE and (best is None or cosine > best[0]):
            best = (cosine, memory_id)
    return (best[1], "embedding_cosine") if best else None


async def _candidate_rows(db_path: str, tokens: set[str]) -> list[tuple[str, str]]:
    """Active rows sharing at least one informative token (FTS5, fallback scan)."""
    match = " OR ".join(f'"{token}"' for token in sorted(tokens))
    async with aiosqlite.connect(db_path) as db:
        try:
            cursor = await db.execute(
                """
                SELECT items.memory_id, items.subject_key || ' ' || items.content
                FROM canonical_memory_fts AS fts
                JOIN canonical_memory_items AS items ON items.memory_id = fts.memory_id
                WHERE canonical_memory_fts MATCH ?
                  AND items.status = 'active'
                  AND (items.expires_at IS NULL OR items.expires_at > datetime('now'))
                ORDER BY bm25(canonical_memory_fts)
                LIMIT ?
                """,
                (match, MAX_CANDIDATE_ROWS),
            )
        except aiosqlite.OperationalError:
            cursor = await db.execute(
                """
                SELECT memory_id, subject_key || ' ' || content
                FROM canonical_memory_items
                WHERE status = 'active'
                  AND (expires_at IS NULL OR expires_at > datetime('now'))
                ORDER BY updated_at DESC
                LIMIT 120
                """
            )
        rows = await cursor.fetchall()
    return [(str(row[0]), str(row[1])) for row in rows]
