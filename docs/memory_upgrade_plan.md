# Memory Upgrade Plan

Agreed direction: governance-first architecture stays; the retrieval layer
gets upgraded incrementally, every change gated by the recall eval. No store
consolidation, no embeddings until the eval says so.

## What shipped in this pass

1. **Recall eval suite** — `memory_recall_eval.py`. 46 cases across exact,
   paraphrase, malay_manglish, voice_noisy, temporal_old, forgotten, absent,
   plus 2 forget over/under-deletion scenarios. Writes JSON reports to
   `logs/evals/`. Exit 1 on hard failures.
2. **FTS5/BM25 hybrid retrieval** — `canonical_memory_fts.py`, wired into
   `search_relevant_canonical_memories`. Tokenizer is `unicode61`, no porter
   stemming (English-only stemming degrades Malay/Manglish). Triggers keep
   the index in sync; backfill runs on init; silently falls back to token
   overlap if the SQLite build lacks FTS5.
3. **Structured save extraction** — `memory_extraction.py`, wired into
   `LearningPipeline`. Off by default. Enable with `MEMORY_EXTRACTION_LIVE=1`
   plus `GOOGLE_API_KEY`. Strict validation: schema, allowed kinds, scope
   pattern, anti-hallucination token-overlap check; any failure falls back to
   the deterministic regex path. Provider `sensitive` is OR-ed with the local
   check, never replaces it. Visibility contract: provider-shaped saves echo
   `(saved as subject -> value)` in the reply.
   Note: enabling extraction can change `kind`/`scope` for new saves, which
   changes canonical `memory_id` hashing for those facts. Old rows are
   unaffected; re-saves of the same content under a new kind create a new
   truth row.
4. **Production watchdog** — `memory_watchdog.py`. Seeds canaries if missing,
   runs leak checks, and alerts when recalls happened in the last 24h with no
   audit events (the silent-audit failure found in review). CLI exits 1 on
   alert. Suggested wiring: launchd daily, or call `memory_watchdog_text()`
   from `/status`.
5. **Forget registry** — `forget_registry.py`. Every store `/forget` covers is
   registered in one place; unregistered stores cannot be forgotten, so new
   stores must register a handler and add an eval scenario. Output format of
   `/forget` is unchanged.

## Baseline (2026-06-09, after FTS5)

| category        | cases | recall@1 | recall@3 |
|-----------------|-------|----------|----------|
| exact           | 10    | 0.90     | 1.00     |
| paraphrase      | 10    | 0.00     | 0.40     |
| malay_manglish  | 7     | 0.00     | 0.71     |
| voice_noisy     | 6     | 0.00     | 1.00     |
| temporal_old    | 3     | 0.67     | 1.00     |

Forgotten leaks: 0/4. False direct recalls on absent facts: 0/6.
Forget scenarios: both pass (no over- or under-deletion).

## After pin-ranking fix (2026-06-09, pin +30 -> +6 tiebreaker)

Pin now guarantees inclusion, not top ranking: any single-token lexical
evidence (+10) outranks an unrelated pinned rule (+6).

| category        | recall@1        | recall@3   |
|-----------------|-----------------|------------|
| exact           | 0.90 -> **1.00**| 1.00       |
| paraphrase      | 0.00 -> **0.20**| 0.40       |
| malay_manglish  | 0.00 -> **0.57**| 0.71       |
| voice_noisy     | 0.00 -> **0.83**| 1.00       |
| temporal_old    | 0.67 -> **1.00**| 1.00       |

recall@3 unchanged by design (same candidate sets, ranking only). All
governance floors still pass. One ranking change, measured, no regressions —
this is the eval suite paying for itself on day one.

Remaining observations:

- voice_noisy@3 is saved by surviving tokens, not typo tolerance; a true
  fuzzy layer (spellfix or trigram) would be needed to finish @1.
- paraphrase@3 (0.40) is now purely a semantic-matching gap; no lexical
  ranking tweak can move it further.

## Decision gates

- **Hard floor (every run):** exact recall@3 >= 0.8, forgotten leaks = 0,
  false direct recalls = 0, forget scenarios pass.
- **Embeddings trigger:** paraphrase@3 < 0.6 or malay@3 < 0.5 while
  exact@3 >= 0.9. **Status: still FIRED after pin fix (paraphrase@3 0.40).**
  The remaining gap is semantic, not ranking. Next retrieval step is an
  embedding rerank: multilingual model required (cross-language Malay->English
  recall is the hard failure mode), local-first preferred, vectors cached in
  SQLite. Implement only with eval before/after numbers.

## Added in second pass

6. **Embedding rerank** — `canonical_memory_embeddings.py`, wired into
   `search_relevant_canonical_memories`. Off by default; enable with
   `MEMORY_EMBED_RERANK_LIVE=1` + `GOOGLE_API_KEY` (model:
   `GEMINI_EMBED_MODEL`, default `gemini-embedding-001`, multilingual —
   cross-language Malay->English recall is the target failure mode).
   Design: gated (skipped when top lexical score >= 20, so exact queries
   never pay an API call), cached (one embedding per memory per content
   revision, stored in `canonical_memory_vectors`), fail-open (provider
   error restores lexical order), and scoped to relevance context only —
   direct-fact recall is never touched. Zero-evidence rows (pure paraphrase
   queries produce no lexical candidates at all) are admitted only when
   cosine >= 0.55 (`ZERO_EVIDENCE_MIN_COSINE`, tune against the live eval).
7. **Extraction shadow mode + divergence audit** — `MEMORY_EXTRACTION_SHADOW=1`
   runs the provider on every explicit save, writes an
   `extraction_divergence` audit event
   (`det=subject->value | prov=subject->value | outcome | mode`), and saves
   the deterministic result. Extraction quality becomes measurable with zero
   behavioral risk. Flip `MEMORY_EXTRACTION_LIVE=1` only when the divergence
   log earns it. Review divergences with:
   `SELECT status_after, source_ref FROM memory_audit_events WHERE event_type='extraction_divergence' ORDER BY id DESC;`

## How to run

```
./venv/bin/python memory_recall_eval.py     # exits 1 on hard failure
./venv/bin/python memory_watchdog.py --db session_history.db   # exits 1 on alert

# Embedding rerank A/B (run both, compare paraphrase/malay numbers):
./venv/bin/python memory_recall_eval.py
MEMORY_EMBED_RERANK_LIVE=1 ./venv/bin/python memory_recall_eval.py
```

## Acceptance criteria

**Keep the embedding rerank only if all of these hold in the live A/B:**

- paraphrase@3 improves meaningfully from 0.40
- malay_manglish@3 improves or stays stable from 0.71
- exact@3 stays >= 0.90
- forgotten leaks stay 0
- absent false direct recalls stay 0

Otherwise tune `ZERO_EVIDENCE_MIN_COSINE` and re-run, or revert the env flag.

**Flip extraction to live only after the shadow log shows it earns it.**
Review dimensions (all in `extraction_divergence` audit rows):

- provider accepted vs rejected rate (`outcome=`)
- fallback reasons (`provider_error` / `no_json` / `validation_failed`)
- subject divergence (`subj_div=1`) and value divergence (`val_div=1`)
- sensitive disagreement (`sens_div=1`) — any case where the provider and
  the local check disagree on sensitivity deserves a manual look
- durability disagreement (`dur_div=1`)
- bad user-visible saves: any time the `(saved as subject -> value)` echo
  had to be corrected by the user counts against going live

## Deliberately not done

- Store consolidation (registry gives the safety property without migration).
- Embeddings (trigger fired; do it next, but measured, not by default).
- Porter stemming, stopword expansion (would help English, hurt Malay).
- Trusting provider extraction without deterministic fallback (never).
