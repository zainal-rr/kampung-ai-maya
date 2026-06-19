# Maya Master Build Status

Date: 2026-06-20

This document records the current build state after the gate benchmark,
reliability ledger, metacognition, and reversibility work. It is a status
snapshot, not a product claim.

## Current Committed Checkpoints

- Gate benchmark current number: Mode B recorded `0/200` attack success against
  no-gate `35/200`. This retires the historical `0/48` number.
- Slack stability rerun: Mode B recorded `0/150` against no-gate `65/150`.
- Step 0 router clearance conformance has an importable registry and smoke that
  ratchets entrypoint, router, command, and delegated surfaces.
- Step 0.5 whole-loop harness exists as a measurement mechanism with replay and
  reduced-form coverage. Replay results are mechanism evidence only unless a real
  provider/lane run is performed.
- Metacognition is bounded by a closed failure taxonomy. Reflection can stop,
  ask, lower confidence, or replan, but must not raise privilege or bypass the
  kernel.
- Step 3 reversibility predicates are wired through the permission kernel.

## What The Results Mean

- AgentDojo measures Maya's W7/kernel/source-trust enforcement layer through
  AgentDojo's own agent loop. It does not exercise the full multi-model Maya
  architecture, planner quarantine, Meet runtime, or cross-lane product router.
- The Step 0.5 replay/reduced harness proves scorer mechanics and selected
  kernel-facing paths. It is not a full blind whole-loop security number until
  reviewer-authored sealed cases run through real lanes/providers.
- Step 3 is a security tightening plus no-regression proof. It preserved already
  free reversible work while making forged/untrusted control values require
  confirmation. It is not a new utility unlock; felt over-gating, if present,
  likely lives above the kernel in router/approval UX.

## Deferred Tests

- Live Telegram spot-checks for any new router path remain manual/live.
- Live Google Meet tests remain deferred until synthetic Meet smokes are green
  and Zainal is ready to admit Maya.
- Provider-backed whole-loop sealed runs remain deferred until explicit approval
  and budget/time are available.
- The old torch-backed Meet live voiceprint scoring path is removed from the
  current design. Remaining audio-wake probes that require optional local audio
  dependencies should be recorded as dependency-blocked, not interpreted as
  product failures.
- Generated reports and eval logs, including `logs/evals/latest.json`, stay
  uncommitted unless explicitly requested.

## Immediate Build Policy

- Safe scaffolding streams may proceed without reviewer lock: router conformance
  ratchets, synthetic Meet tests, and status docs.
- Product behavior changes that loosen authority, disclosure, memory trust, or
  irreversible action gates still require a locked artifact and must-succeed /
  must-fail twins.
- Every benchmark/report must be able to return worse results. Green numbers are
  evidence only when the runner can also report bad news.

## Next Manual Gates

- Review any router conformance diff that changes the registry's active surface
  classification.
- Run the live Telegram spot-check after Step 0b conformance changes land.
- Run synthetic Meet tests before any real Meet voice/capability test.
- Run real Step 0.5 sealed waves only after the real lane/provider binding is
  ready and explicitly approved.
