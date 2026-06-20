from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import aiosqlite

from maya_memory.canonical_memory_embeddings import (
    COSINE_WEIGHT,
    EmbedCall,
    RERANK_CONFIDENCE,
    ZERO_EVIDENCE_MIN_COSINE,
    default_embedding_agent,
    default_embedding_model_name,
    rerank_with_embeddings,
)
from maya_memory.canonical_memory_provenance import ensure_canonical_memory_provenance_schema, resolve_memory_provenance
from maya_memory.canonical_memory_context_items import relevant_items_for_selected
from maya_memory.canonical_memory_direct import search_canonical_direct_fact_impl
from maya_memory.canonical_memory_forget import forget_canonical_memory_impl
from maya_memory.canonical_memory_fts import ensure_canonical_memory_fts, fts_rank_bonuses
from maya_memory.canonical_memory_supersede import (
    archive_superseded_value,
    ensure_supersede_schema,
    load_existing_for_upsert,
    record_supersede_audit,
    should_supersede,
    write_active_memory_row,
)
from maya_memory.canonical_memory_scoring import activation_score
from maya_memory.canonical_memory_text import is_temporary_memory, memory_tokens, subject_key_from_text, value_from_text
from maya_memory.canonical_memory_usage import mark_canonical_used
from maya_memory.memory_audit import record_memory_audit_event
from maya_memory.memory_links import expand_with_neighbors


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
        # W2-A: the unique truth index is PARTIAL (active rows only) so
        # superseded archive rows can share the (kind, subject_key, scope)
        # triple. ensure_supersede_schema owns the migration.
        await ensure_supersede_schema(db)
        await ensure_canonical_memory_provenance_schema(db)
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
    provenance: object | None = None,
) -> str:
    await init_canonical_memory_db(db_path)
    subject_key = subject_key_from_text(content)
    value = value_from_text(content)
    temporary = is_temporary_memory(content, subject_key)
    expires_at = _expiry() if temporary else None
    memory_id = _memory_id(kind, subject_key, scope)
    existing_status = ""
    provenance_json, untrusted_influence, injection_detected = resolve_memory_provenance(provenance, source_channel, source_ref)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        existing, existing_status = await load_existing_for_upsert(
            db, kind, subject_key, scope, memory_id
        )
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
        # W2-A: a changed value archives the prior active row as 'superseded'
        # before the active row is updated in place, so history is not lost.
        superseded_archive = ""
        superseded_prev_content = ""
        if should_supersede(existing, content):
            superseded_prev_content = str(existing["content"])
            superseded_archive = await archive_superseded_value(
                db,
                existing,
                active_memory_id=memory_id,
            )
        await write_active_memory_row(
            db,
            memory_id=memory_id,
            kind=kind,
            subject_key=subject_key,
            content=content,
            value=value,
            scope=scope,
            source_channel=source_channel,
            source_ref=source_ref or raw_text[:180],
            confidence=confidence,
            expires_at=expires_at,
            pinned=pinned,
            temporary=temporary,
            existing_status=existing_status,
            provenance_json=provenance_json,
            untrusted_influence=bool(untrusted_influence),
            injection_detected=bool(injection_detected),
        )
        await db.commit()
    if superseded_archive:
        # Recorded after commit (separate connection) to avoid a write lock on
        # the open upsert transaction.
        await record_supersede_audit(
            db_path,
            archive_id=superseded_archive,
            subject_key=subject_key,
            prev_content=superseded_prev_content,
            source_channel=source_channel,
            source_ref=source_ref or raw_text[:180],
        )
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


async def search_canonical_direct_fact(
    db_path: str,
    query: str,
    limit: int = 3,
    *,
    embedding_agent: EmbedCall | None = None,
) -> list[str] | None:
    await init_canonical_memory_db(db_path)
    return await search_canonical_direct_fact_impl(
        db_path,
        query,
        limit=limit,
        embedding_agent=embedding_agent,
    )


async def search_canonical_direct_fact_with_provenance(
    db_path: str,
    query: str,
    limit: int = 3,
    *,
    embedding_agent: EmbedCall | None = None,
) -> list[dict[str, object]] | None:
    await init_canonical_memory_db(db_path)
    return await search_canonical_direct_fact_impl(
        db_path,
        query,
        limit=limit,
        embedding_agent=embedding_agent,
        include_provenance=True,
    )

async def search_relevant_canonical_memories(
    db_path: str,
    query: str,
    limit: int = 5,
    *,
    embedding_agent: EmbedCall | None = None,
) -> list[str]:
    items = await search_relevant_canonical_memory_items(
        db_path,
        query,
        limit=limit,
        embedding_agent=embedding_agent,
    )
    return [str(item["content"]) for item in items]


async def search_relevant_canonical_memory_items(
    db_path: str,
    query: str,
    limit: int = 5,
    *,
    embedding_agent: EmbedCall | None = None,
) -> list[dict[str, object]]:
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
    # Semantic relevance layer, env-gated and fail-open:
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
    return await relevant_items_for_selected(db_path, selected)


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
    return await forget_canonical_memory_impl(db_path, query)


def _memory_id(kind: str, subject_key: str, scope: str) -> str:
    return f"mem_{hashlib.sha1(f'{kind}:{subject_key}:{scope}'.encode('utf-8')).hexdigest()[:16]}"

def _expiry() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S")
