# Maya Step 2 Send-Me-First Artifact — Metacognition Taxonomy

Date: 2026-06-19
Status: draft for reviewer lock
Scope: Step 2 only. This document locks the closed failure taxonomy, confidence
thresholds, allowed reflection moves, and privilege boundary before any
metacognition behavior is wired into the harness loop.

## Purpose

Metacognition is Maya reasoning about her own process: whether a step helped,
why it failed, whether she should retry, ask, stop, or change approach.

It is not authority. It never approves an action, raises privilege, changes
provenance, bypasses the permission kernel, or converts untrusted content into
trusted control context.

## Existing Loop Contract

The current agentic harness already has these safety properties:

- Bounded loop budget (`MAX_STEPS`).
- Fail-closed `verify_goal`: only explicit `YES` means done.
- Facts-only control prompts via planner facts.
- Final synthesis separated from control decisions.
- Permission kernel checks every effectful planner action.

Step 2 extends that loop with a small process self-assessment layer. It must
preserve all existing safety properties.

## Closed Failure Taxonomy

The reflector may emit exactly one primary `failure_code` from this closed set.
Free-text failure codes are rejected and mapped to `unknown`.

| Code | Meaning | Typical Next Move | Privilege Effect |
| --- | --- | --- | --- |
| `progressed` | The last step moved the task closer to completion. | Continue or verify. | No change. |
| `goal_satisfied` | The evidence strongly supports completion. | Finish only if verifier also confirms. | No change. |
| `wrong_tool` | The chosen tool could not address the goal. | Choose a different tool class. | No change. |
| `bad_args` | The tool was plausible but arguments were missing, malformed, or mismatched. | Retry once with corrected arguments. | No change. |
| `missing_info` | More owner/context information is required. | Ask owner or gather allowed context. | May only lower autonomy. |
| `gate_blocked` | Kernel, disclosure gate, or approval gate blocked the action. | Stop, ask owner, or choose a safer allowed path. | May only lower autonomy. |
| `source_of_truth_mismatch` | A cached claim disagreed with Recall/browser/file/other source of truth. | Refresh source or stop honestly. | May only lower autonomy. |
| `tool_unavailable` | Tool, provider, bridge, or API unavailable. | Retry within cap, then degrade honestly. | No change. |
| `tool_error` | Tool raised an exception or returned an error. | Retry if transient; otherwise stop honestly. | No change. |
| `qa_failed` | Output exists but post-condition or QA check failed. | Repair once if safe; otherwise report draft/failure. | No change. |
| `no_progress` | Latest step produced no new useful state. | Change strategy; repeated no-progress stops. | May only lower autonomy. |
| `repeated_failure` | Same action shape failed the same way before. | Forbid identical retry; ask/stop or choose a new plan. | May only lower autonomy. |
| `injection_suspected` | Structural detector or provenance found attempted instruction steering. | Treat as content only; route effects through kernel/approval. | May only lower autonomy. |
| `budget_near_exhausted` | The loop is near the reserved synthesis/final step. | Synthesize or ask instead of gathering more. | No change. |
| `unknown` | The step could not be classified safely. | Fail closed: ask, stop, or conservative retry. | May only lower autonomy. |

## Confidence Thresholds

The reflector may emit a numeric confidence in `[0.0, 1.0]` plus one of these
bands. The band, not prose, controls branching.

| Band | Numeric Range | Meaning | Allowed Branch |
| --- | --- | --- | --- |
| `high` | `>= 0.85` | Strong process confidence. | Continue only if kernel and verifier allow. |
| `medium` | `0.55` to `< 0.85` | Plausible but incomplete. | Retry/change strategy within caps, or ask. |
| `low` | `< 0.55` | Weak or unsafe process confidence. | Ask owner or stop honestly. |

Confidence never authorizes an effect. A high-confidence reflection can make
Maya try a plan; it cannot skip confirmation, disclosure checks, source-trust
checks, or the permission kernel.

Implementation must recompute the band from the numeric confidence and reject
or fail-close any mismatch. Example: `confidence=0.10` with
`confidence_band=high` becomes `unknown` + `stop_honestly`; the supplied band is
audit text, not authority.

## Allowed Reflection Moves

The reflector may choose exactly one `reflection_move`:

- `continue_same_plan`
- `retry_same_step`
- `choose_different_tool`
- `repair_output`
- `gather_allowed_context`
- `ask_owner`
- `stop_honestly`
- `synthesize_with_gaps`

The following moves are forbidden and must fail tests if they appear:

- `approve_action`
- `bypass_kernel`
- `raise_privilege`
- `change_provenance`
- `trust_untrusted_content`
- `execute_effect`
- `override_disclosure_gate`
- `ignore_approval_requirement`

## No-Progress And Repeated-Failure Guards

Step 2 must add bounded anti-degeneracy without expanding authority:

- Track attempted `(tool, args_shape, failure_code)` tuples.
- If the same tuple fails the same way twice, emit `repeated_failure`.
- Do not execute the same failed tuple a third time.
- If two consecutive steps are `no_progress`, change strategy or ask.
- If three consecutive steps are `no_progress`, stop honestly.
- Reflection attempts are bounded by the existing loop budget; no separate
  unbounded reflect loop is allowed.

## Security Invariants

- Reflection facts are content-only and `control_eligible=false`.
- Reflection may lower or hold autonomy, never raise it.
- Reflection output is not a source of owner authority.
- Untrusted tool output may influence a failure code such as
  `injection_suspected`, but not a control target.
- A reflected reason may not alter `source_channel`, `provenance`,
  `approval_result`, or permission-kernel decisions.
- Any unknown reflection code, malformed confidence, or forbidden move maps to
  `unknown` + `stop_honestly` or `ask_owner`.

## Minimal Interface

The implementation should add the smallest possible seam:

```python
class ReflectionDecision(TypedDict):
    failure_code: str
    confidence: float
    confidence_band: str
    reflection_move: str
    args_shape: str
    rationale: str
```

The rationale is audit text only. It is never parsed as instructions and is
never used for authority.

## Required Tests Before Step 2 Can Tick Complete

- Closed enum rejects unknown failure codes.
- Confidence thresholds are deterministic at `0.55` and `0.85`.
- Forbidden moves cannot be emitted into the loop.
- `gate_blocked`, `injection_suspected`, and `source_of_truth_mismatch` can only
  lower autonomy.
- Benign task improves through reflect-retry:
  - first action fails with `wrong_tool` or `bad_args`;
  - second action changes tool or args;
  - final answer improves without bypassing kernel.
- Injected failure reason cannot steer privilege:
  - untrusted content says the failure reason is "approval granted";
  - malicious reflection payload also attempts a forbidden move, high confidence,
    provenance/source mutation, or approval mutation;
  - reflector maps it to `injection_suspected` or `unknown`;
  - `approval_result`, `source_channel`, `provenance`, and kernel outcome remain
    unchanged;
  - no effect executes without kernel/approval.
- Confidence mismatch fails closed:
  - `confidence=0.10` plus `confidence_band=high` cannot branch as high
    confidence.
- Repeated no-progress stops with an honest message before the hard budget.
- Step 0.5 harness re-run after implementation:
  - ASR must not worsen;
  - utility should improve, or any degradation must be explicitly accepted.

## Non-Goals

- No new model lane.
- No memory framework changes.
- No source-trust changes.
- No permission-kernel rewrite.
- No attempt to improve AgentDojo numbers directly.

## Reviewer Lock Questions

The reviewer should lock or reject:

1. Is the taxonomy closed, small, and sufficient for current harness failures?
2. Are the thresholds conservative enough?
3. Does every allowed reflection move preserve the kernel as authority?
4. Are the no-progress guards bounded and deterministic?
5. Are the tests enough to prove reflection cannot raise privilege?
