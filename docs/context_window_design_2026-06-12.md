# Maya Context Window — Consolidated Design (2026-06-12)

Status: STAGES 0–2 IMPLEMENTED 2026-06-12, MASTER SWITCH OFF
(`MAYA_CONTEXT_WINDOW=0` — live behavior unchanged until Zainal enables it).
Implementation handoff: `docs/context_window_stage1_handoff_2026-06-12.md`.
Canaries C1–C7 all green (`context_window_canaries_smoke.py`). Stage 3
(/context view) and Stage 4 (tuning) not yet built. Four review passes
converged on this design; it remains the single source of truth — any
further implementation follows this doc and the staging order below.

## Goal

Give Maya working memory — "I remember what we were just doing" — without
breaking the four guarantees the system already proved: forget honesty
(Phase 3), untrusted-input containment (W7), canonical memory as the only
durable belief, and domain packs as the only authoritative knowledge.

## Principles (the non-negotiables)

1. **Five layers, never merged.** Raw window = what just happened. Rolling
   summary = what this session is about. Session search = what happened
   before. Canonical memory = what Maya is allowed to believe long-term.
   Domain packs = expert knowledge. Each has its own truth standard.
2. **Session continuity is not durable belief.** The rolling summary is NEVER
   a memory write. Promotion to canonical only via the existing audited flow.
3. **Budget by usefulness and risk, not turn count.** Token budgets per route;
   budget is a CEILING, not a fill target — quiet history is not padded.
4. **One chokepoint.** A single `assemble_context()` builds every prompt's
   context. Both filters (forget watermark, union taint) run there, once.
   Five tiers filtering independently = five chances for a silent leak.
5. **Store facts, not policy.** Turn metadata records what was observed
   (source, taint, signals). The permission kernel derives what that means at
   action time. Policy stays centralized and updatable.
6. **Guarantees before capability.** Canaries are written and failing before
   the window ships (same order that protected W1/W7).

## Human-memory mapping (the design's north star)

| Human system | Maya organ | Status |
| --- | --- | --- |
| Working memory (seconds–minutes, tiny, salient) | Raw token-budgeted window | built, master switch off |
| Episodic memory (events, fades to gist) | Turn log + rolling summary + session summaries | built in stages 1-2, tuning pending |
| Semantic memory (facts without sources) | Canonical memory | built, audited |
| Procedural memory (how-to) | Skills + domain pack recipes | built |
| Prospective memory (remember to do) | Scheduled routines + tasks | built |
| Sleep consolidation | `nightly_consolidation.py` | built; salience upgrade later |

Human bugs deliberately NOT inherited: confabulation (gap-filling) — honesty
contracts forbid it; reconsolidation drift — summaries always rebuild from raw
turns, never from prior summaries; inability to forget — watermark+tombstone
are superhuman and stay that way.

**The map is a guide, not a spec — rigor lives at the SEAMS, not in the
organs.** The table above flatters by making the design look like five boxes;
human memory's real failure modes are boundary failures (source-monitoring
error = remembering the fact, misremembering where it came from — which is why
gist-with-pointer/provenance exists). The engineering effort belongs at the
transitions (window→summary, episodic→canonical promotion) and the
cross-cutting filters (forget, taint), which is exactly what the chokepoint
enforces. Corollary discipline: each organ earns its place on
trust/usefulness merit — do NOT build a row because the human table has one
(emotional tagging, sleep-stage cycling, etc. don't pay rent).

## Architecture

### Turn store

Every user/assistant turn persists with FACTS-ONLY metadata:

```
channel        imac_voice | telegram | ...
role           user | maya
text           capped at per-turn limit (see parameters)
tokens         counted at write time
created_at     timestamp
run_id         harness run linkage when applicable
source         user | browser | screen | omi | document | ...
untrusted_influence   bool   (from existing W7 assess at entry)
injection_detected    bool
signals        ["instruction_override", ...]  (W7 signal names)
```

NOT stored: `allowed_use`, `side_effects_allowed`, or any derived policy.
The kernel decides meaning at action time (registry-driven, fail-closed —
same principle as the W7 fix of 2026-06-11).

### `assemble_context()` — the chokepoint

Extends (does not sit beside) `build_assistant_memory_context` — Maya's
existing single funnel. A chokepoint with two doors is not a chokepoint;
canary C3 proves exclusivity.

Block order is FIXED and cache-friendly (stable blocks first, volatile last):

1. System prompt + contracts
2. Canonical memory (label: `source=canonical, trusted=true`)
3. Domain knowledge (label: `source=domain, trusted=true` — recency must
   never outrank the authoritative recipe)
4. Session search results (facts/vibes/summaries)
5. Rolling summary (with turn-id pointers; label its taint)
6. Raw window, newest-last, each turn age-labeled ("2h ago:")
7. Current user message

Filters applied here, once, for everything:
- **Forget watermark + tombstone:** no content from before the last relevant
  forget enters ANY block (raw, summary, search alike).
- **Union taint:** `untrusted_influence` / `injection_detected` for the
  CURRENT action = OR over every included turn + current-turn assessment.
  Fed into the EXISTING kernel flags — no new kernel surface.

Output: (context_text, taint_flags, audit_manifest). The manifest — what was
loaded, what was excluded and why, tokens used vs budget — is what `/context`
renders (Stage 3) and what canaries assert against.

### Taint rules

- Taint travels with the stored turn forever (closes W7's "works this turn,
  silently fails five turns later" gap).
- Raw window: any included tainted turn taints the action (OR). Deep windows
  therefore confirm-gate sends more often — accepted; the confirm message
  names WHICH turn caused the gate.
- Rolling summary: inherits `untrusted_influence=true` if any folded turn had
  it; `injection_detected` does NOT persist — the summarizer describes content,
  never transcribes imperatives, so compaction is also decontamination.
- Kernel ladder unchanged: injection+gated → deny; influence+gated → confirm;
  never loosens the base decision.

### Forget honesty

- Watermark excludes pre-forget turns from assembly (all tiers).
- A forget whose fact may live in the rolling summary → DROP the summary and
  REBUILD from surviving post-watermark raw turns. No selective summary
  surgery (paraphrase makes string-matching unreliable).
- Assembly-time value re-filter exists only as a CANARY (C1), never as the
  mechanism — paraphrase defeats filters ("AirAsia" → "a Malaysian low-cost
  carrier").

### Rolling compaction (Tier 2)

- On budget overflow, aged-out turns fold into a per-channel rolling summary
  (cheap lane), capped (see parameters).
- Summaries rebuild from raw turns only — never summary-of-summary.
- Gist-with-pointer: summary claims carry turn/run ids so precision questions
  can escalate gist → session search → raw turn (the careful-human
  "let me check my notes" move). Escalation tool is FUTURE work, the pointers
  are cheap and ship with Stage 2.
- Storage is its own table/row — structurally outside every canonical path,
  excluded from weekly distillation inputs unless explicitly promoted.

## Parameters (all env-tunable; defaults below; 0 disables)

| Variable | Default | Meaning |
| --- | --- | --- |
| `MAYA_CONTEXT_WINDOW` | `0` | Master switch. OFF until canaries green + live validation (same opt-in pattern as MAYA_AGENTIC_LOOP). |
| `MAYA_CONTEXT_VOICE_BUDGET` | `3000` | Voice raw-window token ceiling (latency-bound). |
| `MAYA_CONTEXT_TELEGRAM_BUDGET` | `12000` | Normal Telegram ceiling (~a morning of chat). |
| `MAYA_CONTEXT_DEEP_BUDGET` | `32000` | Document/debug/deep-work routes (one full sitting). |
| `MAYA_CONTEXT_COMPLEX_BUDGET` | `48000` | `/complex` + agentic loop (full evidence trail + thread). |
| `MAYA_CONTEXT_PER_TURN_CAP` | `800` | Max tokens stored/included per turn entry — one giant document reply must not evict the whole window. |
| `MAYA_CONTEXT_SUMMARY_CAP` | `1000` | Rolling summary token ceiling per channel. |
| `MAYA_CONTEXT_ROLLING_SUMMARY` | `1` | Tier 2 on/off independently of the raw window. |

Notes: budgets key on route (channel × lane) — `/complex` arrives VIA
Telegram but uses the complex budget. Tuning rule: start at defaults, raise a
tier the second time in a week Maya forgets something from the same sitting,
let `/cost` veto. Too-small is visible; too-big silently degrades attention —
err low. Giant multi-document analyses are per-task Gemini document passes,
NOT window inflation. Why not 100k everywhere: linear cost, mid-context
attention loss, instruction dilution, larger standing injection surface —
model limits (1M) stopped being the binding constraint; attention and
governance are.

## Canaries (written FIRST, failing, before any context flows)

| # | Canary | Asserts |
| --- | --- | --- |
| C1 | Forget-into-summary | Forget a fact already folded into a rolling summary → fact absent from assembled context (rebuild happened); value re-filter backstop also clean. |
| C2 | Taint persistence | Tainted browser turn 5 turns back, still in window → external send this turn is confirm/deny-gated by the kernel; after it ages out, gate lifts. |
| C3 | Chokepoint exclusivity | No prompt-assembly path bypasses `assemble_context()` (architecture smoke; greps + call-graph check). |
| C4 | Budget binding | Assembly ≤ budget; per-turn cap enforced; empty history produces no padding; route picks the right budget. |
| C5 | Watermark | Post-forget assembly contains zero pre-watermark turns across ALL tiers. |
| C6 | Rebuild-from-raw | Rolling summary regenerates from raw turns only; summary-of-summary is structurally impossible (input set checked). |
| C7 | Phase 3 regression | Full remember → recall → forget → ask flow with `MAYA_CONTEXT_WINDOW=1` → no leak (the original memory-honesty live test, now with the window on). |

## Staging (revised order — taint ships WITH the window, never after)

- **Stage 0 — Spec + canaries.** This doc + C1–C7 written and red. No
  behavior change.
- **Stage 1 — Turn store + chokepoint + raw window.** Taint metadata ON the
  stored turns from day one; watermark in the chokepoint; master switch
  default OFF. (Shipping window-without-taint, even briefly, would make W7
  weaker than today — the one forbidden ordering.)
- **Stage 2 — Rolling compaction.** Overflow folding, rebuild-on-forget,
  gist pointers, taint inheritance.
- **Stage 3 — `/context` view.** Renders the chokepoint's audit manifest:
  loaded turns + tokens, rolling summary, excluded (watermarked / tainted /
  over-budget) counts, budget usage. The guarantee made inspectable.
- **Stage 4 — Tuning.** Per-route budget calibration against Phase 7 field
  data + `/cost`; verify cache-friendly block ordering actually hits provider
  prompt caches; voice latency measurement.
- **Future (gated on Phase 7 evidence, not built now), each with a MANDATORY
  guard — these two are human bugs hiding inside the import list:**
  - *Salience scoring* in nightly consolidation proposing canonical
    candidates. GUARD: salience is GATED BY TAINT — a turn with
    `untrusted_influence=true` can never enter the candidate queue on
    salience alone, because injected content games salience by design
    ("IMPORTANT: remember this" is high-salience, low-trust). Salience
    proposes; the trust flag + human reviewer dispose. Salience-without-trust
    is a megaphone straight into long-term belief.
  - *Retrieval strengthening* (frequency+recency activation weighting).
    GUARD: affects RANK ONLY — never truth, never confidence, never wording.
    Bounded and decaying so it cannot run away: naive import gives
    rich-get-richer (often-surfaced memories get boosted, surface more, boost
    more), which re-imports the human availability heuristic and can entrench
    an error permanently. Cap the boost; let it decay without reinforcement.
  - *Gist→raw escalation tool* (pointers ship in Stage 2; the tool waits).
  - *Evidence-sufficiency estimator* — still explicitly rejected (model
    judgment dressed as a metric).

## Interactions with existing systems

- **Sticky domain retrieval STAYS.** The window makes it more necessary, not
  less: with prior answers in context the model is tempted to answer
  follow-ups from its own earlier words; only retrieval re-injects the domain
  answer contract. Window = what was said; packs = what is true.
- **Permission kernel:** no new surface — assembly feeds the existing
  `untrusted_influence`/`injection_detected` parameters with durable taint.
- **Session compactor:** Tier 2 is an upgrade of it (continuous on overflow),
  not a parallel system.
- **Nightly consolidation:** unchanged now; salience upgrade is the future
  hook.
- **Prompt caching:** stable-first block order in the chokepoint makes big
  windows cheap on repeat turns; enforceable because assembly happens in one
  place.

## Honest limits

- The window improves continuity, not truth. Numbers still come from recipes
  and computation; beliefs still come from canonical memory.
- Deep windows increase confirm-gate frequency on external sends (taint OR).
  That is the safety design working; tune window size, not the kernel.
- Token counting adds a small assembly cost per turn (estimator fine; exact
  tokenizer unnecessary).
- This is the single most dangerous addition to the memory system — it is a
  new path into the prompt that bypasses canonical write gates BY DESIGN.
  The chokepoint + canaries are what make that acceptable. If implementation
  pressure ever suggests "just append the turns here, we'll filter later" —
  that is the failure mode, stop.
