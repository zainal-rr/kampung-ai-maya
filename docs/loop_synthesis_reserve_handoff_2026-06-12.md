# Agentic Loop — Synthesis Reserve + Early-Answer Bias (Handoff, 2026-06-12)

Input: Phase 6 refinement finding — the in-loop finance synthesis retrieved
correctly but the loop kept gathering until the 8-step budget hit and ended
with the honest-but-empty budget message instead of an answer.

Design (agreed with Zainal): deterministic gate where the guarantee matters,
prompt contract where judgment helps.

## Part 1 — Synthesis reserve (deterministic guarantee)

The FINAL budgeted step is no longer the planner's to spend. When the loop
reaches `current_step >= max_steps - 1` with the goal unsatisfied, the graph
forces a synthesis action instead of asking the planner for another tool call.

Flow: `_plan` → `_at_synthesis_reserve(state)` true → `synthesize_final_answer`
(new hook in `harness_llm_planner.py`) produces the best answer the gathered
evidence supports, with a prompt that REQUIRES naming evidence gaps and forbids
inventing facts → action becomes `{"done": True, "answer": <synthesis>}` →
normal done-path delivers it. The run records a `synthesis_reserve` trace
event ("step N of M").

Safety net preserved: if the synthesis call fails or returns empty, the loop
falls through to the planner (which itself fail-closes to done), and `_finish`
still applies the honest budget-exhausted message. The W1 net stays underneath
the reserve — `_finish` only skips the generic message when a forced synthesis
actually produced the final response (`forced_synthesis` flag, declared in
`HarnessState` so LangGraph propagates it between nodes).

## Part 2 — Early-answer bias (prompt rule, no machinery)

`choose_next_action`'s prompt now (a) shows the budget — "Steps used: N of M
(the final step is reserved for answer synthesis)" — and (b) carries one rule:
"Prefer finishing over gathering: once the domain knowledge and at least one
observation cover the goal, choose done and write the answer now - further
browsing or observing has diminishing value."

Deliberately NOT built: an evidence-sufficiency estimator. That is a model
judgment dressed as a metric; Phase 7 data should justify it first.

## Files changed

| File | Change |
| --- | --- |
| `harness_llm_planner.py` | NEW `synthesize_final_answer(state, llm_call, knowledge)`; `choose_next_action` prompt gains budget note + prefer-finishing rule |
| `harness_helpers/graph_runner.py` | `_at_synthesis_reserve` helper; reserve branch in `_plan` (after `_forced_agentic_action`, which keeps priority — a goal-completing send still beats synthesis); `_finish` clobber-guard; `synthesize_final_answer` import |
| `harness_state.py` | `forced_synthesis: bool` declared in `HarnessState` (LangGraph drops undeclared keys between nodes — this WAS the first-run bug, caught by the smoke) |
| `harness_agentic_deep_smoke.py` | `_scripted_planner` gains a `synthesis` reply (triggered by the "This is the FINAL" prompt marker); NEW `_synthesis_reserve_path` test; `_budget_exhaustion_path` re-pointed to the synthesis-failure fallback |

## Verification (sandbox, 2026-06-12)

`harness_agentic_deep_smoke`: 14/14 ok, including:
- `synthesis reserve (final step lands a real answer)` — planner never says
  done, verify always NO, max_steps=3 → final response EQUALS the scripted
  synthesis text, no budget-message clobber, `synthesis_reserve` in trace.
- `budget exhaustion fallback (synthesis failed -> honest message)` — same
  scenario with empty synthesis → the original honest budget message returns.

Unaffected smokes re-run green: `skill_domain_smoke`,
`domain_router_precedence_smoke`, `document_species_smoke`.

## iMac contained live-style verification (2026-06-12)

Ran the finance domain-synthesis prompt through `HarnessRouter` with
`MAYA_AGENTIC_LOOP=1` only for the subprocess, using a contained DB at
`logs/phase6_synthesis_retest.db` so the running Maya service stayed in its
resting state.

Prompt:

```text
search online for current preference share market norms and assess our issuance feasibility against them
```

Result:

- Run `hrn_90e5e47f76d4`, workflow `browser`, status `completed`.
- `current_step`: `8`.
- `domain_knowledge`: `finance_credit_analysis`.
- `synthesis_reserve`: recorded at `step 8 of 8`.
- Final answer was a grounded preference-share investor feasibility assessment
  with explicit evidence limitations, not the generic budget-exhausted message.

This proves the reserve catches the original Phase 6 failure mode. The browser
still only exposed Google result-page text for that run, so the answer correctly
named missing live-market benchmark evidence instead of inventing it.

## iMac verification steps

1. Pull/sync; `./venv/bin/python -m py_compile harness_llm_planner.py harness_helpers/graph_runner.py harness_state.py`.
2. `./venv/bin/python harness_agentic_deep_smoke.py` → expect 14 ok lines.
3. Full CI if you want the 57-smoke sweep.
4. Live retest (loop on temporarily: `MAYA_AGENTIC_LOOP=1`, restart):
   - Rerun the Phase 6 domain-synthesis case:
     `search online for current preference share market norms and assess our issuance feasibility against them`
   - EXPECT: a real final assessment (grounded, gaps named) instead of the
     budget message. Trace should show either an early `done` (Part 2 bias
     worked) or a `synthesis_reserve` event (Part 1 caught it at the cap).
   - Check: `sqlite3 session_history.db "SELECT event, details FROM harness_events WHERE event IN ('synthesis_reserve','loop_iteration') ORDER BY id DESC LIMIT 12;"`
   - Optional second case: the EPF multi-step prompt should now finish in
     FEWER steps than before (early-answer bias) — compare loop_iteration counts.
5. Return to resting state: `MAYA_AGENTIC_LOOP=0`, restart.

## Honest limits

- Part 2 is a prompt nudge; the planner may still over-gather. Part 1 is the
  guarantee — worst case is now "best answer from partial evidence, honestly
  caveated" instead of "no answer".
- The synthesis call costs one extra planner-lane invocation on capped runs
  (runs that finish early never pay it).
- `_forced_agentic_action` outranks the reserve by design: if the goal is
  "send the file" and the file exists, sending IS the synthesis.
