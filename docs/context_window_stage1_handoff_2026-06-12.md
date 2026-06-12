# Context Window Stages 0–2 — Implementation Handoff (2026-06-12)

Spec: `docs/context_window_design_2026-06-12.md` (the contract; read first).
Everything below is LIVE-INERT: `MAYA_CONTEXT_WINDOW` defaults to `0` and
canary C0 proves OFF is a no-op (not even table creation). No restart needed;
nothing changes until the switch is flipped deliberately.

## What was built

### `context_window.py` (NEW — Tier 1 + Tier 2)

- **Turn store** `context_turns`: channel, role, content (per-turn capped at
  write), token estimate, source, `untrusted_influence`, `injection_detected`,
  signals, folded flag, run_id, timestamp. FACTS ONLY — no stored policy.
- **`assemble_recent_context(db, channel=, route=)`** — THE chokepoint for
  window content. Applies both filters once: forget watermark + union taint.
  Returns `AssembledContext(text, untrusted_influence, injection_detected,
  manifest)`; the manifest (included/excluded/tokens/budget) is the Stage 3
  `/context` view's data source, already produced.
- **Rolling summary** `context_rolling_summary` (per channel): overflow turns
  fold automatically after each recorded turn, against the channel's own
  budget. Deterministic gist for now (oldest lines decay first); an LLM
  summarizer can be injected later without changing the contract. Summary
  inherits `untrusted_influence`, never raw injected text — compaction is
  decontamination. Summaries rebuild from raw turns only.
- **Forget watermark** `context_watermarks`: stores the LAST TURN ID at
  forget time — not a timestamp. (Canary C5 caught the bug on first run:
  SQLite's second-resolution clock cannot order a forget against turns in the
  same second. Turn-id ordering is deterministic.) `on_canonical_forget` also
  drops all rolling summaries; survivors re-fold from raw.

### Wiring (three points, all guarded by the OFF switch)

| File | Change |
| --- | --- |
| `storage.py` | `save_history_message` (the existing single funnel for ALL turns — 7 call sites) now also records a context turn; new optional kwargs `source`/`untrusted_influence`/`injection_detected` for future W7 entry-tagged callers. |
| `canonical_memory.py` | `forget_canonical_memory` calls `on_canonical_forget` AFTER a successful forget (match count > 0). No-match forgets do NOT watermark — they would erase working memory for nothing. |
| `assistant_memory_context.py` | `build_assistant_memory_context` (Maya's existing context funnel) appends the assembled window LAST (volatile-last block order per the design's cache rule). |

### `context_window_canaries_smoke.py` (NEW — the guarantee set)

C0 switch-off no-op · C1 forget-into-summary (fold the fact, forget, assert
no resurrect) · C2 taint persistence (tainted turn 5 turns back → kernel
gates `telegram.send_file`; influence survives folding; watermark lifts the
gate) · C3 chokepoint exclusivity (greps the repo: assembly is called from
exactly one place) · C4 budget binding (ceiling not fill target; routes
differ; empty history = no padding) · C5 watermark (id-ordered) ·
C6 rebuild-from-raw (no summary-of-summary) · C7 the full Phase 3
remember→forget→ask flow through the REAL paths (storage funnel + canonical
forget hook) with the window ON — no leak.

## Verification on the iMac

1. `./venv/bin/python -m py_compile context_window.py storage.py canonical_memory.py assistant_memory_context.py`
2. `./venv/bin/python context_window_canaries_smoke.py` → 8 ok lines.
3. Full CI — expect previous suite green + this new smoke (storage and
   canonical_memory were touched; their existing smokes are the regression
   net and passed in the sandbox: intake guard, untrusted boundary, skill
   usage, domain, agentic deep, species).
4. NO live test needed — the switch is off; live behavior is unchanged.
   (Sandbox verified: 7 adjacent smokes + canaries all green, 2026-06-12.)

## When you decide to enable it (deliberately, post-Phase 7 or during)

1. Re-run the canaries on the iMac that morning.
2. Set `MAYA_CONTEXT_WINDOW=1`, restart.
3. The window starts EMPTY (recording is also gated by the switch) — Maya
   warms up over the first conversation, like a fresh day.
4. Live spot-checks: ask something, then "what did I just ask you?" →
   answered from window. Then the Phase 3 honesty flow live: remember →
   recall → forget → ask → must not resurrect (C7's live twin).
5. Watch `/cost` for prompt-size growth; budgets are env-dials
   (`MAYA_CONTEXT_*_BUDGET`) — tune low-first per the design's asymmetry rule.
6. Rollback: `MAYA_CONTEXT_WINDOW=0`, restart. Tables persist harmlessly.

## Honest limits / open items (tracked, deliberate)

- **Taint tagging at the chat funnel is mechanical, not yet live-fed:** the
  funnel accepts taint kwargs, and C2 proves the gating composition, but the
  assistant reply path does not yet pass real W7 flags when a reply was built
  from browser/screen content (same split as the original W7 entry-tagging
  work — the flags exist on observations; threading them to the reply-save
  call is the follow-up wiring item). Until then, chat-path turns record as
  trusted; harness-path taint continues to flow through the existing
  observation channel unchanged.
- **Kernel flags from assembly are computed but not yet consumed by chat-path
  actions** (the chat path has no kernel-gated sends today; harness actions
  keep their own taint state). When a chat-path external action exists,
  `AssembledContext.untrusted_influence/injection_detected` are the inputs.
- **Window rides the existing `should_use_full_context` gate** — turns that
  skip full context (cheap/fast paths) also skip the window. Revisit when
  enabling: follow-ups like "yes do it" may be exactly where the window helps.
- **Deterministic gist quality is basic** (first-120-chars lines). Good
  enough to prove the contract; the LLM summarizer upgrade slots in without
  schema change.
- Stage 3 (`/context` view rendering the manifest) and Stage 4 (budget tuning
  + cache-order verification) are NOT built — by design, they follow field
  evidence.
