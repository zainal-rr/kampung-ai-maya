# Nightly Dedup + Association Guards — Verification Protocol

Date: 2026-06-11. Base commit: `eb239b7` (Add nightly memory consolidation).
Written so a fresh session can verify every change independently.

## Why this pass exists

Inspection of the first scheduled nightly run (`night-2026-06-10`, 5 saved /
1 rejected / 2 links) found three issues:

1. **Duplicate accretion.** The distiller phrases facts as full sentences, so
   `subject_key_from_text` mints a unique key per phrasing
   (e.g. `user_prefers_maya_never_uses_dash_symbols_in_any_responses`) and the
   `(kind, subject_key, scope)` truth-key dedup never fires. All 5 night-1
   saves were semantic duplicates of rules already in the DB. Untreated, every
   active night re-saves rephrasings.
2. **Temporary-row side door.** `expand_with_neighbors` filtered status and
   expiry but not `temporary`/`test_marker`, so a link could resurface a test
   memory the lexical path deliberately excludes.
3. **Neighbor displacement.** `neighbor_score = top_score - 2` let one
   association outrank the 2nd/3rd true lexical hits and push them out of the
   top-3 prompt context.

## Change inventory (exact)

### C1 + C2 — memory_links.py (guards, both read and write side)
- `expand_with_neighbors` JOIN WHERE clause: added
  `AND items.temporary = 0 AND items.test_marker = 0`.
- `_active_ids` (used by `add_memory_link` endpoint validation): added the
  same two conditions, so links to temporary/test rows are *refused at
  creation* and *filtered at read* (defense in both directions).

### C3 — canonical_memory.py (`_with_association_neighbors`)
- Before: `neighbor_score = max(1, scored[0][0] - ASSOCIATION_NEIGHBOR_PENALTY)`
  (strongest candidate minus 2).
- After: `weakest_selected = scored[: max(limit, 1)][-1][0]` then
  `neighbor_score = max(1, weakest_selected - ASSOCIATION_NEIGHBOR_PENALTY)`.
- Effect: neighbors rank strictly below every candidate that would be
  selected, so they fill spare context slots only and can never displace a
  lexical/FTS hit from the top-`limit` cut.

### C4 — canonical_memory_dedup.py (NEW, 113 lines)
`find_semantic_duplicate(db_path, content, embed_agent=None)`
→ `(memory_id, reason) | None`. Layered, cheapest first:
- Candidates: FTS5 match on the content's informative tokens, active +
  unexpired rows only, capped 24 (fallback without FTS: 120 newest active).
- Layer 1 `token_containment`: duplicate when >= 0.8 of the candidate's
  tokens appear in an existing row AND >= 0.5 of that row's tokens appear in
  the candidate (the reverse bound prevents short rows swallowing long facts).
- Layer 2 `embedding_cosine` (only when `embed_agent` provided, fail-open):
  cosine >= 0.86 against candidates, best match wins.
- Guards: skips contents with < 3 informative tokens; uncertain = NOT a
  duplicate (false positive silently drops a new fact — worse than keeping a
  duplicate).

### C5 — nightly_consolidation.py (dedup gate in the save loop)
- New imports: `find_semantic_duplicate`, `default_embedding_agent`,
  `mark_canonical_used`.
- Gate position: after the stability filter + forgotten-subject check,
  before `upsert_canonical_memory`.
- On duplicate: `mark_canonical_used([dup_id], event_type="activation",
  source_ref="nightly_dedup:<run_key>:<reason>")` (reinforces the existing
  row), plus audit event `weekly_reject` with
  `source_ref="semantic_duplicate:<reason>"`. Fact is NOT inserted.
- `NightlyConsolidationResult` gained `deduped: int` (after `saved`).
  NOTE: `deduped` appears in the stdout JSON only; the
  `nightly_consolidation_runs` table schema was not changed.
- Embed agent comes from `default_embedding_agent()` — env-gated by
  `MEMORY_EMBED_RERANK_LIVE=1` + `GOOGLE_API_KEY`. Without it the gate is
  token-only (still catches night-over-night rephrasings; cross-phrasing
  dupes like "never uses dash symbols in any responses" vs "Do not use dash
  symbols in replies" need the embedding layer).

### C6 — nightly_consolidation_helpers.py (`distiller_prompt`)
- Added one instruction line telling the distiller to phrase facts as
  `<short subject> is/are <value>` rather than full "the user..." sentences,
  so future subject keys can actually collide.

### memory_links_smoke.py (NEW, 5 named invariants)
- I1 `temporary_link_refused`: `add_memory_link` returns False for a
  temporary endpoint in either direction; durable-durable succeeds.
- I2 `temporary_never_expands`: a link to a temporary row force-inserted via
  raw SQL (bypassing I1) still never surfaces through
  `expand_with_neighbors`; a legitimate neighbor does.
- I3 `no_displacement`: 3 strong lexical hits + 1 linked neighbor; top-3
  context contains only the lexical hits; at limit=5 the neighbor fills a
  spare slot.
- I4 `dedup_token`: a rephrasing of a seeded fact returns
  `("…", "token_containment")`.
- I5 `dedup_no_false_positive`: a genuinely new fact returns None.

## Verification commands (any session, no API keys needed)

```
./venv/bin/python memory_links_smoke.py          # expect: memory_links_smoke: ok
./venv/bin/python nightly_consolidation_smoke.py # expect: PASS … (unchanged)
./venv/bin/python canonical_memory_smoke.py      # expect: ok
./venv/bin/python memory_recall_eval.py          # expect: ok, association
                                                 #   {'recall_at_3': 1.0, 'direct_leaks': 0,
                                                 #    'forgotten_neighbor_leaks': 0}
```

Verified in this pass (2026-06-11, sandbox): memory_links_smoke,
nightly_consolidation, canonical_memory, canonical_memory_embeddings,
memory_control, memory_soak, memory_time_audit, memory_perspective,
skill_memory, memory_extraction, memory_watchdog, self_heal_memory,
weekly_memory, weekly_memory_provider_path — all pass. Eval: 48 cases + 2
forget scenarios, all hard gates green, numbers unchanged from `eb239b7`
baseline (exact@1 1.0, paraphrase@3 0.4, association 1.0/0/0).

## Live verification after the next 2:30 AM run

```
# 1. Dedup actually fired (if the day rehashed known preferences):
grep -o '"deduped": [0-9]*' logs/nightly-memory.stdout.log | tail -1
sqlite3 session_history.db "SELECT source_ref, content_preview FROM memory_audit_events
  WHERE source_ref LIKE 'semantic_duplicate:%' ORDER BY id DESC LIMIT 10;"

# 2. No new sentence-key duplicates of the night-1 style rows:
sqlite3 session_history.db "SELECT count(*) FROM canonical_memory_items
  WHERE source_channel='nightly_consolidation' AND status='active';"
# Expect: 5 (unchanged) unless genuinely NEW facts were learned.

# 3. No link touches a temporary/test row:
sqlite3 session_history.db "SELECT count(*) FROM memory_links l
  JOIN canonical_memory_items s ON s.memory_id=l.source_memory_id
  JOIN canonical_memory_items t ON t.memory_id=l.target_memory_id
  WHERE s.temporary=1 OR s.test_marker=1 OR t.temporary=1 OR t.test_marker=1;"
# Expect: 0 for links created after this change.
```

## Known limitations / deliberate non-actions

- The 5 night-1 duplicate rows were KEPT: they are well-phrased and future
  rephrasings will dedupe against them. Removing the older learning-pipeline
  versions is a separate cleanup decision.
- Token-only mode (no embed agent) will not catch cross-phrasing duplicates;
  enable `MEMORY_EMBED_RERANK_LIVE=1` to arm layer 2.
- `deduped` is not persisted in `nightly_consolidation_runs` (stdout JSON +
  audit rows only). Add a column later if trend tracking is wanted.
- One existing duplicate subject pair in the live DB
  (`current_desk_setup_mouse`, 2 active rows across kinds) predates this
  change and was not touched.

## Pre-existing failure found during regression (NOT from this pass)

`hermes_memory_smoke.py` fails in the current working tree:
`AttributeError: 'KampungAssistant' object has no attribute '_maybe_curate_memory'`.
Cause: the uncommitted `assistant.py` refactor moved the method to
`assistant_post_route.maybe_curate_memory`, but `hermes_memory_smoke.py:55`
still calls `maya._maybe_curate_memory(...)`. Verified to pass at commit
`eb239b7` via a clean worktree. Fix belongs with the in-progress assistant
refactor, not this memory pass.
