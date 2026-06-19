# Maya Master Build Status — 2026-06-20

This is the current engineering status for the Maya master build path. It records what has been implemented, what each result proves, and what remains deferred or reviewer-gated. Generated eval logs are intentionally not part of this document.

## Headline State

- Gate benchmark: current Maya W7/kernel/source-trust gate measured `0/200` attack success in Mode B against `35/200` no-gate control. This measures the gate layer through AgentDojo's loop, not full multi-model Maya.
- Slack stability check: Mode B held `0/150` against no-gate `65/150`.
- Step 0 router conformance: conformance scaffolding and ratchets are present; live Telegram spot-check passed on a gated disclosure path.
- Step 0.5 whole-loop harness: mechanism/reduced-form evidence only. It is not yet a full live blind pass through all real lanes and provider calls.
- Step 3 reversibility: kernel predicates are wired as security tightening with no friction regression. This did not unlock new utility because the kernel already allowed the reversible cases.
- Step 4 pattern recognition: implemented as harness-side method hints only, with enum-shaped patterns, no control-value fields, `control_eligible=false`, and poison tests that exercise the real kernel backstop.
- Step 5 Meet: synthetic conversation-hold and presentation-sanitizer coverage added. Live Meet check is approved but must end with `/leave`, status verification, and closing any Meet/output/browser tabs opened for the test.
- Step 6 memory integrity: native integrity smoke added over real memory paths. Provider-backed LongMemEval remains deferred unless a runnable LongMemEval dataset/runner config is supplied.
- Step 7 honesty: honesty-under-attack smoke added. Scores are self-authored until reviewer scoring is validated.

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

## Deferred Or Reviewer-Gated

- Live Meet validation:
  - approval is recorded;
  - requires an actual Meet target/session;
  - cleanup rule: send `/leave`, verify `/meetstatus` is ended/stopped, remove Maya from the meeting, and close tabs/browsers opened for the test.
- Provider-backed LongMemEval:
  - approval is recorded;
  - no local LongMemEval runner/dataset config was found in this repo state;
  - when supplied, run through real Maya memory and stamp commit, provider/model, split, command, and timestamps.
- Step 0.5 full live blind harness:
  - current result is reduced-form/mechanism evidence;
  - a publishable whole-loop number requires reviewer-authored sealed probes through real lanes/providers.
- Step 6 and Step 7 scoring:
  - integrity and honesty suites are self-authored;
  - numbers should not be presented externally until reviewer scoring is validated.

## Reporting Caveats

- AgentDojo results describe Maya's W7/kernel/source-trust enforcement layer only. They do not exercise the full four-lane/multi-model architecture, planner quarantine, or cross-lane disclosure paths.
- A zero observed ASR should always travel with its denominator and no-gate baseline.
- Whole-loop harness results must say whether they were replay, reduced-form, or real live lane runs.
- Meet results must distinguish synthetic tests from live meeting behavior.
- Memory and honesty scores must state whether they are self-authored or independently verified.
- Absence of incidents means “no incidents observed,” not “reliable.”

## Current Proof Commands

- `./venv/bin/python tests/smokes/meet_synthetic_feature_smoke.py`
- `./venv/bin/python tests/smokes/memory_integrity_smoke.py`
- `./venv/bin/python tests/smokes/honesty_under_attack_smoke.py`
- `./venv/bin/python local_ci.py`
