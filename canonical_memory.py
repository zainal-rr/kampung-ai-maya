from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import aiosqlite

from canonical_memory_embeddings import (
    COSINE_WEIGHT,
    EmbedCall,
    RERANK_CONFIDENCE,
    ZERO_EVIDENCE_MIN_COSINE,
    default_embedding_agent,
    default_embedding_model_name,
    rerank_with_embeddings,
)
from canonical_memory_fts import ensure_canonical_memory_fts, fts_rank_bonuses
from canonical_memory_scoring import activation_score
from canonical_memory_text import is_temporary_memory, memory_tokens, subject_key_from_text, value_from_text
from canonical_memory_usage import mark_canonical_used
from memory_audit import record_memory_audit_event
from memory_links import expand_with_neighbors


_INITIALIZED: set[str] = set()
ASSOCIATION_NEIGHBOR_PENALTY = 2


async def init_canonical_memory_db(db_path: str) -> None:
    if db_path in _INITIALIZED:
        return
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS canonical_memory_items (
                memory_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                subject_key TEXT NOT NULL,
                content TEXT NOT NULL,
                value TEXT DEFAULT '',
                scope TEXT DEFAULT 'global',
                source_channel TEXT DEFAULT '',
                source_ref TEXT DEFAULT '',
                confidence TEXT DEFAULT 'medium',
                status TEXT DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_used_at DATETIME,
                reinforcement_count INTEGER DEFAULT 0,
                expires_at DATETIME,
                pinned INTEGER DEFAULT 0,
                temporary INTEGER DEFAULT 0,
                test_marker INTEGER DEFAULT 0
            )
            """
        )
        await db.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_canonical_memory_truth
            ON canonical_memory_items(kind, subject_key, scope)
            """
        )
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_canonical_memory_status
            ON canonical_memory_items(status, updated_at DESC)
            """
        )
        try:
            await db.execute("ALTER TABLE canonical_memory_items ADD COLUMN reinforcement_count INTEGER DEFAULT 0")
        except aiosqlite.OperationalError:
            pass
        await ensure_canonical_memory_fts(db)
        await db.commit()
    _INITIALIZED.add(db_path)


async def upsert_canonical_memory(
    db_path: str,
    *,
    raw_text: str,
    content: str,
    kind: str,
    scope: str,
    source_channel: str,
    confidence: str,
    source_ref: str = "",
    pinned: bool = False,
    allow_resurrect: bool = True,
) -> str:
    await init_canonical_memory_db(db_path)
    subject_key = subject_key_from_text(content)
    value = value_from_text(content)
    temporary = is_temporary_memory(content, subject_key)
    expires_at = _expiry() if temporary else None
    memory_id = _memory_id(kind, subject_key, scope)
    existing_status = ""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        existing = await (
            await db.execute(
                """
                SELECT status
                FROM canonical_memory_items
                WHERE kind = ? AND subject_key = ? AND scope = ?
                """,
                (kind, subject_key, scope),
            )
        ).fetchone()
        existing_status = str(existing["status"]) if existing else ""
        if existing_status == "forgotten" and not allow_resurrect:
            # Derived writers (weekly distillation, ambient Omi context) must
            # never recreate a fact the user explicitly forgot.
            await record_memory_audit_event(
                db_path,
                event_type="canonical_write_blocked_forgotten",
                memory_id=memory_id,
                subject_key=subject_key,
                status_before="forgotten",
                status_after="forgotten",
                source_channel=source_channel,
                source_ref=source_ref or raw_text[:180],
                content=content,
            )
            return memory_id
        await db.execute(
            """
            INSERT INTO canonical_memory_items (
                memory_id, kind, subject_key, content, value, scope,
                source_channel, source_ref, confidence, status, expires_at,
                pinned, temporary, test_marker, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(kind, subject_key, scope) DO UPDATE SET
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
                source_ref or raw_text[:180],
                confidence,
                expires_at,
                int(pinned),
                int(temporary),
                int(temporary),
            ),
        )
        await db.commit()
    await record_memory_audit_event(
        db_path,
        event_type="canonical_update" if existing_status else "canonical_write",
        memory_id=memory_id,
        subject_key=subject_key,
        status_before=existing_status,
        status_after="active",
        source_channel=source_channel,
        source_ref=source_ref or raw_text[:180],
        content=content,
    )
    return memory_id


async def search_canonical_direct_fact(db_path: str, query: str, limit: int = 3) -> list[str] | None:
    await init_canonical_memory_db(db_path)
    subject_key = subject_key_from_text(query)
    if not subject_key:
        return []
    query_tokens = memory_tokens(subject_key)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        active = await db.execute(
            """
            SELECT memory_id, subject_key, content
            FROM canonical_memory_items
            WHERE status = 'active'
              AND (expires_at IS NULL OR expires_at > datetime('now'))
            ORDER BY updated_at DESC
            """
        )
        rows = [row for row in await active.fetchall() if _direct_fact_match(query_tokens, subject_key, row["subject_key"], row["content"])][:limit]
        if not rows:
            forgotten = await db.execute(
                """
                SELECT subject_key, content FROM canonical_memory_items
                WHERE status IN ('forgotten', 'expired', 'superseded')
                ORDER BY updated_at DESC
                """
            )
            if any(_direct_fact_match(query_tokens, subject_key, row["subject_key"], row["content"]) for row in await forgotten.fetchall()):
                return None
    await mark_canonical_used(
        db_path,
        [str(row["memory_id"]) for row in rows],
        event_type="canonical_recall",
        source_ref=query,
    )
    return [str(row["content"]) for row in rows]

def _direct_fact_match(query_tokens: set[str], subject_key: str, row_subject: str, row_content: str) -> bool:
    return row_subject == subject_key or (
        len(query_tokens) >= 2 and query_tokens.issubset(memory_tokens(f"{row_subject} {row_content}"))
    )

async def search_relevant_canonical_memories(
    db_path: str,
    query: str,
    limit: int = 5,
    *,
    embedding_agent: EmbedCall | None = None,
) -> list[str]:
    await init_canonical_memory_db(db_path)
    tokens = memory_tokens(query)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        fts_bonuses = await fts_rank_bonuses(db, query)
        cursor = await db.execute(
            """
            SELECT memory_id, content, subject_key, pinned, temporary, updated_at,
                   COALESCE(reinforcement_count, 0) AS reinforcement_count
            FROM canonical_memory_items
            WHERE status = 'active'
              AND (expires_at IS NULL OR expires_at > datetime('now'))
            ORDER BY pinned DESC, updated_at DESC
            """
        )
        rows = await cursor.fetchall()
    scored = []
    zero_evidence: list[tuple[int, str, str]] = []
    spread_seed_ids: list[str] = []
    for row in rows:
        memory_id = str(row["memory_id"])
        haystack = f"{row['subject_key']} {row['content']}"
        overlap = len(tokens & memory_tokens(haystack))
        fts_bonus = fts_bonuses.get(memory_id, 0)
        score = activation_score(
            overlap=overlap,
            pinned=bool(row["pinned"]),
            reinforcement_count=int(row["reinforcement_count"]),
            updated_at=str(row["updated_at"] or ""),
        ) + fts_bonus
        if row["temporary"] and overlap == 0 and not fts_bonus:
            continue
        if overlap > 0 or row["pinned"] or fts_bonus:
            scored.append((score, memory_id, str(row["content"])))
            if overlap > 0 or fts_bonus:
                spread_seed_ids.append(memory_id)
        elif not row["temporary"]:
            zero_evidence.append((0, memory_id, str(row["content"])))
    scored.sort(key=lambda item: item[0], reverse=True)
    # Semantic layer, env-gated and fail-open. Two roles, both limited to
    # relevance context (direct-fact recall is never touched):
    # 1) rerank weak lexical candidates;
    # 2) admit zero-evidence rows (pure paraphrase / cross-language queries
    #    produce no lexical candidates at all) only when cosine clears
    #    ZERO_EVIDENCE_MIN_COSINE. Embedder failure restores lexical order.
    agent = embedding_agent if embedding_agent is not None else default_embedding_agent()
    if agent is not None and (not scored or scored[0][0] < RERANK_CONFIDENCE):
        pool = scored + zero_evidence[:48]
        zero_ids = {memory_id for _score, memory_id, _content in zero_evidence}
        floor = int(ZERO_EVIDENCE_MIN_COSINE * COSINE_WEIGHT)
        reranked = await rerank_with_embeddings(
            db_path, query, pool, agent, model=default_embedding_model_name()
        )
        scored = [
            item for item in reranked
            if item[1] not in zero_ids or item[0] >= floor
        ]
    scored = await _with_association_neighbors(db_path, scored, spread_seed_ids, limit)
    selected = scored[:limit]
    await mark_canonical_used(
        db_path,
        [memory_id for _, memory_id, _content in selected],
        event_type="activation",
        source_ref=query,
    )
    return [content for _, _memory_id, content in selected]


async def _with_association_neighbors(
    db_path: str,
    scored: list[tuple[int, str, str]],
    spread_seed_ids: list[str],
    limit: int,
) -> list[tuple[int, str, str]]:
    """Add one-hop associated memories to relevance context, fail-open.

    Only lexical/FTS evidence can seed spreading activation. Direct-fact recall
    does not use this path, and memory_links itself joins active rows only.
    """
    if not scored or not spread_seed_ids or limit <= 0:
        return scored
    seed_id_set = set(spread_seed_ids)
    ordered_seeds = [memory_id for _score, memory_id, _content in scored if memory_id in seed_id_set][:limit]
    if not ordered_seeds:
        return scored
    try:
        neighbors = await expand_with_neighbors(db_path, ordered_seeds, limit=limit)
    except Exception:
        return scored
    if not neighbors:
        return scored
    seen = {memory_id for _score, memory_id, _content in scored}
    # Score below the weakest candidate that would be selected, not the
    # strongest: associations fill spare context slots and trail behind every
    # lexical/FTS hit, never displacing one from the top-`limit` cut. (The
    # old top-score-minus-2 let one neighbor outrank the 2nd/3rd true hits.)
    weakest_selected = scored[: max(limit, 1)][-1][0]
    neighbor_score = max(1, weakest_selected - ASSOCIATION_NEIGHBOR_PENALTY)
    expanded = list(scored)
    for memory_id, content in neighbors:
        if memory_id in seen:
            continue
        seen.add(memory_id)
        expanded.append((neighbor_score, memory_id, content))
    expanded.sort(key=lambda item: item[0], reverse=True)
    return expanded

async def forget_canonical_memory(db_path: str, query: str) -> int:
    await init_canonical_memory_db(db_path)
    subject_key = subject_key_from_text(query)
    tokens = memory_tokens(subject_key or query)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT memory_id, subject_key, content
            FROM canonical_memory_items
            WHERE status = 'active'
            """
        )
        rows = await cursor.fetchall()
        matches = []
        for row in rows:
            content = str(row["content"])
            if subject_key and row["subject_key"] == subject_key:
                matches.append(dict(row))
            elif tokens and tokens.issubset(memory_tokens(f"{row['subject_key']} {content}")):
                matches.append(dict(row))
        for row in matches:
            await db.execute(
                """
                UPDATE canonical_memory_items
                SET status = 'forgotten', updated_at = CURRENT_TIMESTAMP
                WHERE memory_id = ?
                """,
                (str(row["memory_id"]),),
            )
        await db.commit()
    for row in matches:
        await record_memory_audit_event(
            db_path,
            event_type="canonical_forget",
            memory_id=str(row["memory_id"]),
            subject_key=str(row["subject_key"]),
            status_before="active",
            status_after="forgotten",
            source_channel="memory_control",
            source_ref=query,
            content=str(row["content"]),
        )
    if matches:
        # Forget honesty spans ALL memory tiers: watermark the context window
        # and drop rolling summaries so a forgotten fact cannot resurface from
        # working memory (docs/context_window_design_2026-06-12.md, C1/C5).
        # A no-match forget does NOT watermark — it would erase working memory
        # for nothing.
        from context_window import on_canonical_forget

        await on_canonical_forget(db_path)
    return len(matches)


def _memory_id(kind: str, subject_key: str, scope: str) -> str:
    return f"mem_{hashlib.sha1(f'{kind}:{subject_key}:{scope}'.encode('utf-8')).hexdigest()[:16]}"

def _expiry() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S")
