# Maya Master Build Status — 2026-06-20

This is the current engineering status for the Maya master build path. It records what has been implemented, what each result proves, and what remains deferred or reviewer-gated. Generated eval logs are intentionally not part of this document.

## Headline State

- Gate benchmark: current Maya W7/kernel/source-trust gate measured `0/200` attack success in Mode B against `35/200` no-gate control. This measures the gate layer through AgentDojo's loop, not full multi-model Maya.
- Slack stability check: Mode B held `0/150` against no-gate `65/150`.
- Step 0 router conformance: conformance scaffolding and ratchets are present; live Telegram spot-check passed on a gated disclosure path.
- Step 0.5 whole-loop harness: Wave 1 full binding completed with reviewer-authored blind probes, real Gemini reader, real GPT/OpenAI planner, real Maya kernel, and a safe fake effect sink. Result: `0/45` unsafe runs; `35/45` secure/useful and `10/45` secure/not-useful. It still does not execute real external sends/payments/deletes or live Meet/Telegram effects.
- Step 3 reversibility: kernel predicates are wired as security tightening with no friction regression. This did not unlock new utility because the kernel already allowed the reversible cases.
- Step 4 pattern recognition: implemented as harness-side method hints only, with enum-shaped patterns, no control-value fields, `control_eligible=false`, and poison tests that exercise the real kernel backstop.
- Step 5 Meet: synthetic conversation-hold and presentation-sanitizer coverage added. Live Meet check is approved but must end with `/leave`, status verification, and closing any Meet/output/browser tabs opened for the test.
- Step 6 memory integrity: native integrity smoke added over real memory paths. Provider-backed LongMemEval remains deferred unless a runnable LongMemEval dataset/runner config is supplied.
- Step 7 honesty: honesty-under-attack smoke added. Scores are self-authored until reviewer scoring is validated.
- C0 capability baseline: current reversible-loop baseline ran against the real OpenAI planner/evaluator path on `maya_domain_capability_v1`. Corrected outcome counts: `6/30` success, `6/30` partial, `9/30` fail, `9/30` honest_stop. OpenClaw/Claw-SWE-Bench is not locally configured and is recorded as deferred.

## Implemented Evidence

- Meet synthetic coverage proves:
  - conversation hold can answer follow-ups without changing authority;
  - close phrase and idle timeout drop the hold;
  - echo does not open or refresh hold;
  - mid-hold actions still route to owner approval;
  - private meeting disclosure remains approval/refusal-gated;
  - planted active presentation markup is stripped (`script`, iframe, form, event handlers, and remote loads).
- Memory integrity coverage proves:
  - owner-set memory recalls with owner provenance;
  - relayed external content is stored as reference-only untrusted memory;
  - untrusted taint survives prompt-context construction;
  - superseded values do not win current recall;
  - forgotten supersede chains do not resurrect through history;
  - untrusted recalled values cannot silently authorize an external effect.
- Honesty coverage proves:
  - claimed-done-but-missing artifact emits `false_success_risk`;
  - wrong/stale artifact body emits `artifact_context_mismatch`;
  - source-of-truth mismatch and unchecked cached state emit incidents;
  - provider-down and loop-budget failures surface legible owner-visible messages;
  - disclosure refusal is explicit;
  - blocked/empty browser extraction is partial/honest, while bluffing success fails.
- Step 0.5 Wave 1 full binding proves:
  - the blind probes ran through the real reader-to-planner-to-kernel path, not deterministic replay;
  - the safe fake sink is not acting as a defense: it records an executed effect only after the kernel returns `allow`;
  - every attack case remained secure across 3 runs;
  - most attack cases were secure because the laundered effect was not proposed upstream, with the kernel/sink retained as an observable backstop rather than the primary blocker in those runs;
  - the 10 secure/not-useful outcomes were concentrated in strict answer-fragment utility checks, not unsafe effects.
- C0 capability baseline proves:
  - the current reversible loop is measurable before building C1-C6;
  - answer-type scoring uses a semantic evaluator path rather than literal fragment matching;
  - artifact creation is currently the weakest measured area: local artifact tasks produced `2` partials and `7` failures, mostly approval pauses, timeouts, or tool/remap failures;
  - browser-read tasks stopped honestly because the local browser bridge was unavailable in the run;
  - trace-grounded bottleneck attribution is still too sparse: `unknown` was `20/30`, so C0 should improve instrumentation before using reason-code counts as the sole C1-C6 ranking.

## Deferred Or Reviewer-Gated

- Live Meet validation:
  - approval is recorded;
  - requires an actual Meet target/session;
  - cleanup rule: send `/leave`, verify `/meetstatus` is ended/stopped, remove Maya from the meeting, and close tabs/browsers opened for the test.
- Provider-backed LongMemEval:
  - approval is recorded;
  - no local LongMemEval runner/dataset config was found in this repo state;
  - when supplied, run through real Maya memory and stamp commit, provider/model, split, command, and timestamps.
- Step 0.5 remaining gaps:
  - Wave 1 is now real-provider/full-binding evidence for reader, planner, kernel, and safe sink;
  - Wave 1 does not exercise real external effect execution, live Google Meet audio, or real Telegram/file delivery;
  - Wave 1 cases are now spent as blind evidence; future product changes need a new sealed wave for fresh blind claims;
  - reflection-channel coverage should still be confirmed specifically for the A2-style failure-reason probe, because a passing run may avoid the reflection branch by never failing upstream.
- Step 6 and Step 7 scoring:
  - integrity and honesty suites are self-authored;
  - numbers should not be presented externally until reviewer scoring is validated.
- C0 capability follow-up:
  - generated report is intentionally left under `logs/evals/c0/` and uncommitted;
  - before C1-C6, improve C0 progress reporting and reason attribution enough to reduce the `unknown` bucket;
  - the clearest measured capability bottleneck is reversible local artifact creation friction/timeouts, not boundary security.

## Reporting Caveats

- AgentDojo results describe Maya's W7/kernel/source-trust enforcement layer only. They do not exercise the full four-lane/multi-model architecture, planner quarantine, or cross-lane disclosure paths.
- A zero observed ASR should always travel with its denominator and no-gate baseline.
- Whole-loop harness results must say whether they were replay, reduced-form, full binding, or real live lane/effect runs.
- Step 0.5 Wave 1 should be described as full binding over real reader/planner/kernel with safe fake effects, not as reduced planner/kernel-only evidence.
- Meet results must distinguish synthetic tests from live meeting behavior.
- Memory and honesty scores must state whether they are self-authored or independently verified.
- C0 capability results must state whether semantic answers were model-evaluated, human-reviewed, or still awaiting review. Do not compare C0 to OpenClaw until the OpenClaw adapter/probe is actually configured.
- Absence of incidents means “no incidents observed,” not “reliable.”

## Current Proof Commands

- `./venv/bin/python tests/smokes/meet_synthetic_feature_smoke.py`
- `./venv/bin/python tests/smokes/memory_integrity_smoke.py`
- `./venv/bin/python tests/smokes/honesty_under_attack_smoke.py`
- `./venv/bin/python tests/smokes/c0_capability_baseline_smoke.py`
- `./venv/bin/python scripts/run_c0_capability_baseline.py --planner openai-if-available --evaluator openai-if-available --out logs/evals/c0/<report>.json`
- `./venv/bin/python local_ci.py`
