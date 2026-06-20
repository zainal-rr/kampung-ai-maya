# Maya Stability Floor — 2026-06-20

This document defines the local stability floor after the Maya portfolio and
capability work. It is intentionally boring: no new features, no live surfaces,
and no provider calls. The goal is to know whether the repository is stable
enough to work on today.

## Local Stability Command Set

Use the project virtual environment. In a sibling worktree that does not have
its own ignored `venv/`, use the original checkout's interpreter.

```bash
./venv/bin/python tests/smokes/reliability_incident_ledger_smoke.py
./venv/bin/python tests/smokes/reliability_scorecard_smoke.py
./venv/bin/python tests/smokes/router_clearance_conformance_smoke.py
./venv/bin/python tests/smokes/whole_loop_harness_smoke.py
./venv/bin/python tests/smokes/memory_integrity_smoke.py
./venv/bin/python tests/smokes/honesty_under_attack_smoke.py
./venv/bin/python tests/smokes/c0_capability_baseline_smoke.py
./venv/bin/python tests/smokes/meet_synthetic_feature_smoke.py
./venv/bin/python tests/smokes/pattern_recognition_smoke.py
./venv/bin/python tests/smokes/agentic_artifact_fast_path_smoke.py
./venv/bin/python tests/smokes/harness_agentic_deep_smoke.py
./venv/bin/python local_ci.py
```

## Current Result

Last run: 2026-06-20 on `codex/stability-hardening`.

- Focused stability smokes: pass.
- Fast `local_ci.py`: `87/87` pass, `blocking failures: 0`.
- Fresh-worktree assumptions fixed:
  - local CI no longer writes the scored eval canary to tracked `logs/evals/latest.json`;
  - latest demo evidence validates from the tracked latest index even when ignored historical replay logs are absent;
  - the UI read API smoke creates a temporary read-only SQLite fixture instead of requiring a local `session_history.db`.

## Generated Files

Do not commit generated local reports unless explicitly requested.

- `logs/evals/latest.json` is tracked for intentional public proof snapshots.
- `local_ci.py` writes its canary report to ignored `logs/evals/local_ci_latest.json`.
- Memory recall evals may write ignored timestamped reports under `logs/evals/`.
- Live browser, agentic, Meet, Telegram, and provider evidence remain generated runtime logs.

## Deferred / Live-Only Proof

These are not part of the local stability floor:

- live browser reliability nights;
- live agentic reliability nights;
- live Telegram checks;
- live Google Meet checks;
- provider-backed LongMemEval;
- `local_ci.py --live-providers`;
- extended replay tiers unless preparing a release or nightly gate.

Passing the local floor means deterministic code paths are healthy. It does not
prove long-term operational uptime or live account behavior.
