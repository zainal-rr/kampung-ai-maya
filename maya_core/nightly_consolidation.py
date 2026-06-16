from __future__ import annotations

"""Nightly sleep-consolidation for Maya's memory.

Additive module: nothing imports this yet, so Maya's behavior is unchanged
until this is run deliberately (manually or from a future launchd job).

The cycle per night, two provider calls maximum:

1. Zero-delta skip: no new history rows since the last completed run means
   no provider calls at all (quiet days and travel days cost nothing).
2. Replay the day's episodes from `history` (sensitive rows excluded, capped).
3. ONE distiller call returns facts AND association links in a single JSON.
4. The reviewer gates facts with the same contract as weekly memory.
5. Approved facts are saved with allow_resurrect=False, so forgotten
   facts stay forgotten — the existing guard, unchanged.
6. Links are recorded only between active canonical memories (memory_links).
7. Decay report: stale unused unpinned memories are LISTED, never mutated.
   Acting on decay stays a human decision until trust is earned.

Audit reuses the existing weekly_* event types with
source_channel="nightly_consolidation", so memory_audit.py needs no change
and `/memory inspect` shows nightly activity immediately.
"""

import argparse
import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from maya_memory.canonical_memory import init_canonical_memory_db, upsert_canonical_memory
from maya_memory.canonical_memory_dedup import find_semantic_duplicate
from maya_memory.canonical_memory_embeddings import default_embedding_agent
from maya_memory.canonical_memory_usage import mark_canonical_used
from maya_memory.memory_links import init_memory_links_db
from maya_core.nightly_consolidation_helpers import (
    audit_nightly,
    decay_report,
    distiller_prompt,
    finish_run,
    gather_episodes,
    init_nightly_db,
    last_watermark,
    parse_links,
    record_costs,
    record_links,
)
from weekly_memory_live import (
    ProviderCall,
    _clean,
    _forgotten_subject_exists,
    _parse_facts,
    _parse_review,
    _review_prompt,
    _stable_fact,
)

DEFAULT_DECAY_DAYS = 45
DEFAULT_DB_PATH = "session_history.db"


@dataclass(frozen=True)
class NightlyConsolidationResult:
    run_key: str
    skipped: bool = False
    skip_reason: str = ""
    saved: int = 0
    deduped: int = 0
    rejected: int = 0
    links_recorded: int = 0
    links_dropped: int = 0
    provider_calls: int = 0
    memory_ids: tuple[str, ...] = ()
    confirmation_needed: tuple[str, ...] = ()
    reviewer_error: str = ""
    decay_candidates: tuple[str, ...] = ()


async def run_nightly_consolidation(
    db_path: str,
    *,
    distiller_agent: ProviderCall | None,
    reviewer_agent: ProviderCall | None = None,
    run_key: str = "",
    decay_days: int = DEFAULT_DECAY_DAYS,
    require_reviewer: bool = True,
) -> NightlyConsolidationResult:
    await init_canonical_memory_db(db_path)
    await init_nightly_db(db_path)
    await init_memory_links_db(db_path)
    run_key = run_key or datetime.now(timezone.utc).strftime("night-%Y-%m-%d")
    watermark = await last_watermark(db_path)
    episodes, new_watermark = await gather_episodes(db_path, watermark)
    decay = await decay_report(db_path, decay_days)
    if not episodes:
        return await _finish_skip(db_path, run_key, new_watermark or watermark, "no new episodes since last run", decay)
    if distiller_agent is None:
        return await _finish_skip(db_path, run_key, watermark, "no distiller configured", decay)
    if require_reviewer and reviewer_agent is None:
        return await _finish_skip(db_path, run_key, watermark, "reviewer required but not configured", decay)

    try:
        raw = await distiller_agent(distiller_prompt(run_key, episodes))
    except Exception as exc:
        await finish_run(
            db_path,
            run_key,
            status="failed",
            watermark=watermark,
            episodes=len(episodes),
            skip_reason=f"distiller_error: {type(exc).__name__}: {exc}"[:500],
        )
        raise
    provider_calls = 1
    facts = _parse_facts(raw)
    proposed = list(facts)
    links = parse_links(raw)
    for fact in proposed:
        await audit_nightly(db_path, "weekly_candidate", run_key, fact)

    confirmation_needed: tuple[str, ...] = ()
    rejected = 0
    reviewer_error = ""
    if reviewer_agent:
        provider_calls += 1
        try:
            reviewed = await reviewer_agent(_review_prompt(run_key, facts))
        except Exception as exc:  # degrade safe: zero unreviewed canonical writes
            reviewer_error = f"{type(exc).__name__}: {exc}"
            rejected = len(facts)
            for fact in facts:
                await audit_nightly(db_path, "weekly_reject", run_key, fact, source_ref=reviewer_error)
            facts = []
            links = []
        else:
            review = _parse_review(reviewed, proposed_count=len(facts))
            facts = review["facts"]
            rejected = int(review["rejected"])
            confirmation_needed = tuple(review["confirmation_needed"])
            approved = {_clean(fact.get("content", "")) for fact in facts}
            for fact in proposed:
                if _clean(fact.get("content", "")) not in approved:
                    await audit_nightly(db_path, "weekly_reject", run_key, fact, source_ref="review_rejected")

    saved = 0
    deduped = 0
    memory_ids: list[str] = []
    embed_agent = default_embedding_agent()
    for fact in facts:
        content = _clean(fact.get("content", ""))
        kind = _clean(fact.get("kind", "")) or "lesson"
        scope = _clean(fact.get("scope", "")) or "global"
        if not _stable_fact(content, kind=kind, scope=scope) or await _forgotten_subject_exists(db_path, content):
            rejected += 1
            await audit_nightly(db_path, "weekly_reject", run_key, fact, source_ref="stability_filter")
            continue
        # Semantic dedup gate: the truth key never collides for full-sentence
        # subject keys, so rephrasings of an existing fact would otherwise
        # insert a new row every night. A confident duplicate reinforces the
        # existing row instead of inserting.
        duplicate = await find_semantic_duplicate(db_path, content, embed_agent=embed_agent)
        if duplicate:
            duplicate_id, reason = duplicate
            await mark_canonical_used(
                db_path, [duplicate_id],
                event_type="activation",
                source_ref=f"nightly_dedup:{run_key}:{reason}",
            )
            await audit_nightly(
                db_path, "weekly_reject", run_key, fact,
                memory_id=duplicate_id, source_ref=f"semantic_duplicate:{reason}",
            )
            deduped += 1
            continue
        memory_id = await upsert_canonical_memory(
            db_path,
            raw_text=content,
            content=content,
            kind=kind,
            scope=scope,
            source_channel="nightly_consolidation",
            confidence=_clean(fact.get("confidence", "")) or "medium",
            source_ref=run_key,
            allow_resurrect=False,
        )
        await audit_nightly(db_path, "weekly_save", run_key, fact, memory_id=memory_id)
        memory_ids.append(memory_id)
        saved += 1

    links_recorded, links_dropped = await record_links(db_path, links)
    await record_costs(db_path, distiller_agent, reviewer_agent)
    await finish_run(
        db_path, run_key, status="completed", watermark=new_watermark or watermark,
        episodes=len(episodes), saved=saved, rejected=rejected,
        links_recorded=links_recorded, provider_calls=provider_calls,
    )
    return NightlyConsolidationResult(
        run_key=run_key, saved=saved, deduped=deduped, rejected=rejected,
        links_recorded=links_recorded, links_dropped=links_dropped,
        provider_calls=provider_calls, memory_ids=tuple(memory_ids),
        confirmation_needed=confirmation_needed, reviewer_error=reviewer_error,
        decay_candidates=decay,
    )


async def _finish_skip(
    db_path: str, run_key: str, watermark: str, reason: str, decay: tuple[str, ...]
) -> NightlyConsolidationResult:
    await finish_run(db_path, run_key, status="skipped", watermark=watermark, skip_reason=reason)
    return NightlyConsolidationResult(run_key=run_key, skipped=True, skip_reason=reason, decay_candidates=decay)


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Run one nightly memory consolidation pass.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    parser.add_argument("--run-key", default="")
    parser.add_argument("--decay-days", type=int, default=DEFAULT_DECAY_DAYS)
    parser.add_argument("--live", action="store_true", help="Use real provider keys (Gemini distiller, Claude reviewer).")
    parser.add_argument(
        "--allow-unreviewed",
        action="store_true",
        help="Allow provider facts to save when Claude review is unavailable. Off by default for autonomous safety.",
    )
    args = parser.parse_args()
    distiller = reviewer = None
    if args.live:
        from maya_core.weekly_memory_providers import weekly_distiller_agent, weekly_reviewer_agent

        distiller = weekly_distiller_agent()
        reviewer = weekly_reviewer_agent()
    result = await run_nightly_consolidation(
        args.db, distiller_agent=distiller, reviewer_agent=reviewer,
        run_key=args.run_key, decay_days=args.decay_days,
        require_reviewer=not args.allow_unreviewed,
    )
    print(json.dumps(result.__dict__, default=str, indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
