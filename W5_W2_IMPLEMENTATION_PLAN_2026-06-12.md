# W5 (Execution Sandbox) + W2 (Retrieval Intelligence) — Implementation Plan

> **SUPERSEDED (2026-06-12, same day):** the live spec is
> `docs/blast_radius_and_retrieval_design_2026-06-12.md` (canaries-first,
> verified tool surface, Artisan in W5-1 scope, confidence-triggered W2-B
> fallback). This file is kept as the earlier, broader draft — the
> broker/sandbox-exec material here becomes relevant only at the W5-2
> OS-enforcement tier. Do not implement from this file.

Date: 2026-06-12. Companion to `MAYA_SWOT_COUNCIL_2026-06-12.md` (rev 2) and
`MAYA_WEAKNESS_STATUS_2026-06-11.md`.

Doctrine constraints honored throughout: every phase lands behind an env flag
(default off), is proven by smoke + eval before any default flip, extends the
forget/canary discipline, and respects checklist 25.5 — **do not raise autonomy
on unsandboxed host execution**.

What already exists (verified in tree, build on it — do not duplicate):

- W5: `tool_sandbox_policy.py` risk classes (READ_ONLY / FILE_WRITE / REPO_WRITE /
  BROWSER_AUTOMATION / EXTERNAL / destructive) live in the permission kernel;
  `secret_provider.py` with Keychain migrated; isolated-worktree self-heal pattern.
  Missing piece = **enforced containment**: execution still runs with full user
  privileges. Policy decides; nothing contains.
- W2: `memory_recall_eval.py` (59 cases) + compare harness; FTS5/BM25 hybrid
  (`canonical_memory_fts.py`); neighbor boost live; `canonical_memory_embeddings.py`
  vector cache + rerank (env-gated, off — evals showed no gain); partial supersede
  (newer value wins direct recall); `forget_registry.py`. Paraphrase recall@3 = 0.5
  is the headline gap; temporal validity windows don't exist.

---

## Track W5 — from policy to containment

Order by blast radius (per the weakness doc): shell → file writes/deletes →
repo → browser. Secrets finish line at the end.

### W5-P0 — Single execution chokepoint (no behavior change)

1. Inventory every side-effect execution site: `grep -rn "subprocess\|os.system\|Popen"`
   plus file-write paths in office builders, and the browser driver.
2. Route all of them through one `execution_broker.py` (or extend the
   `MayaToolRegistry` executor). The broker takes (tool, args, risk_class,
   kernel decision) and is the only place that actually spawns/writes.
3. CI gate in the style of `legacy_architecture_removed_smoke.py`: no direct
   `subprocess` import outside the broker and an allowlist of legacy files
   that shrinks each session.

Exit: broker exists, smoke green, behavior byte-identical. This phase is the
multiplier — every later phase attaches to one place.

### W5-P1 — Shell containment (highest risk reduction per effort)

1. Wrap shell-class tools in a macOS `sandbox-exec` profile (deprecated but
   functional — Chromium/Bazel still use it): write allowlist = Maya workspace
   (`~/Desktop/Maya`), per-run `/tmp` dir; deny everything else including
   `~/.ssh`, `~/Library`; network deny by default, opt-in per tool risk class.
2. Env scrubbing: child processes get a minimal environment — **no API keys**.
   Keychain provider makes this natural: keys are fetched in-process, never
   exported to children.
3. Flag `MAYA_SANDBOX=1`, kill-switch drill like the agentic loop had.
4. `sandbox_escape_smoke.py`: attempted write outside allowlist, attempted
   network from a local-only tool, attempted read of `~/.ssh` — all must fail
   loudly. These are the W5 equivalent of memory canaries; keep them green forever.

### W5-P2 — File writes and deletes

1. Broker enforces the FILE_WRITE path allowlist mechanically (today it is
   doctrine, not code).
2. Deletes become quarantine-not-delete: move to `~/Desktop/Maya/.trash/<date>/`
   with a 14-day sweep. Approval flow unchanged; blast radius now reversible.

### W5-P3 — Repo writes

Make the isolated-worktree pattern mechanical: the broker refuses REPO_WRITE
outside an isolated worktree; apply-back remains approval-gated. (Doctrine
already says this; enforcement moves it from discipline to physics.)

### W5-P4 — Browser blast radius (decision required)

W7 gates intent; this phase caps damage when gating fails.

1. **Decision point:** dedicated Chrome profile for untrusted/general agentic
   browsing (no saved logins, no payment autofill), real profile reserved for
   your trusted frequent-sites catalog. The extension bridge can bind to a
   specific profile window. Recommended: tainted or unknown domains → Maya
   profile; `frequent_sites_catalog` domains → real profile.
2. Downloads land in a quarantine dir; opening a downloaded file is a
   FILE_WRITE-class action through the broker.

### W5-P5 — Secrets finish line

After a 1-week soak: flip `MAYA_SECRET_PROVIDER` default to `keychain`, strip
real values from `.env` (keep `.env.example`), audit `config.get_env` callers.

**Track exit criteria:** escape smokes green across P1–P4, kill switch proven,
one honest week of field use with `MAYA_SANDBOX=1`, then default ON. Only after
that should any autonomy increase (deeper loop budget, more reachable tools)
be considered — 25.5 ordering.

---

## Track W2 — retrieval that feels like she knows you

Key diagnosis the evals already support: **rerank failed because candidates
fail earlier.** Rerank only reorders what lexical/FTS retrieval finds; when a
paraphrase shares no tokens, the right row never enters the candidate set, so
there is nothing to rerank. Fix candidate generation, not ranking.

### W2-P0 — Eval expansion from real misses (data first)

1. Mine `session_history.db` for real questions that missed: recall queries
   with no/poor result followed by a rephrase. These become eval cases —
   real paraphrase pairs beat invented ones.
2. Add temporal-history cases: "what was my rent before?", "what did I used to
   prefer?" — currently unanswerable by design (overwrite).
3. Target ≥100 cases. The eval suite is the contract for every later flip.

### W2-P1 — Embedding candidate retrieval (the big one)

1. Reuse `canonical_memory_vectors` (cache + hashing already built). At query
   time: embed the query, pull top-k by cosine, **union** with lexical/FTS
   candidates, then run the existing scoring + (now useful) rerank.
2. Governance guard, extending the existing `ZERO_EVIDENCE_MIN_COSINE` rule:
   vector-only candidates may enter relevance context but may **not** win
   direct-fact recall without lexical corroboration — preserves the
   no-false-direct-recall property the eval enforces.
3. Forget integration: register a `forget_registry` handler that deletes the
   vector row; add a **vector-leak canary** (forgotten fact must not be
   reachable via embedding search). This is the W2 step most likely to be
   forgotten and the one your canary culture exists for.
4. Embedding writes happen at save time (async, cached by content hash);
   query embedding is one call — set a latency budget (<150ms added) and log
   cost to the cost tracker.
5. Flag `MEMORY_VECTOR_CANDIDATES=1`. Flip default only if: paraphrase
   recall@3 ≥ 0.8 (from 0.5), Malay/Manglish ≥ 0.85, zero forgotten leaks,
   zero absent-fact false recalls, latency inside budget.

### W2-P2 — Supersede with validity windows (temporal truth)

1. Schema: add `valid_from`, `valid_to`, `superseded_by` to canonical rows.
   Updates mark the old row superseded instead of overwriting. Direct recall
   returns current; "before / previously / last time" retrieves the chain.
2. Forget covers the whole chain: forgetting a fact forgets its ancestors
   (canary case: superseded ancestor must not leak after forget).
3. Weekly memory and audit rows record supersede events (`canonical_supersede`).
4. This closes the "my rent was X, now Y" silent-history-loss gap — the same
   capability Zep's temporal graph sells, built inside your governance model.

### W2-P3 — Malay/Manglish + voice-noise normalization (small, data-driven)

Query-side synonym/normalization map fed only by real misses from P0 mining —
no hand-invented dictionaries. The unicode61-no-stemming decision stays.

### W2-P4 — Entity graph: stays deferred

Correct call at one-user scale. Revisit only if P1+P2 evals still show
association misses.

**Track exit criteria:** expanded eval green at the targets above, all
canaries (including the two new ones: vector-leak, chain-forget) green, then
flip `MEMORY_VECTOR_CANDIDATES` default on and document in the checklist.

---

## Sequencing across both tracks

| Order | Item | Why first |
| --- | --- | --- |
| 1 | Commit the working tree | Checklist sign-off names it; everything below needs a rollback point |
| 2 | W5-P0 broker + W2-P0 eval mining | Both are no-behavior-change; can run as parallel sessions |
| 3 | W2-P1 vector candidates | Biggest daily-felt improvement; eval harness already waiting |
| 4 | W5-P1 shell containment | Biggest risk reduction; unblocks future autonomy increases |
| 5 | W2-P2 supersede windows | Schema migration — do after P1 lands to avoid double migration churn |
| 6 | W5-P2/P3 file + repo enforcement | Mechanical follow-through |
| 7 | W5-P4 browser profile decision | Needs your call on the dual-profile trade-off |
| 8 | W5-P5 secrets flip + soak reviews | Finish line |

Phase 7 (field-use week) can and should run concurrently from step 3 onward —
its disappointment list will re-prioritize W2-P3 content and validate W5
ergonomics (a sandbox that blocks legitimate work gets disabled; better to
learn that during soak than after default-on).
