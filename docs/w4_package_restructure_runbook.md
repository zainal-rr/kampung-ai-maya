# W4 Package Boundary Restructure Runbook

Current as of 2026-06-17.

## Status

W4 moves runtime implementation out of the repository root and keeps the daily
operator commands at the root as real CLI wrappers. Waves 1 through 5 are built:
smokes/replays/evals now live under `tests/`, runtime modules live under
packages, and preserved root commands execute package entrypoints with
`runpy.run_module(..., run_name="__main__")` or their own `main()`.

Wave 6 and final acceptance still require a clean worktree and final CI pass.

## Current Proof Commands

Run these from the repo root:

```bash
./venv/bin/python local_ci.py
./venv/bin/python code_health.py
./venv/bin/python browser_extension_bridge.py --status
python -c "import kampung_ai_app"
```

`browser_extension_bridge.py --status` is query-only. A successful wrapper proof
means the command reaches the packaged bridge status code. The `client_connected`
field is volatile live Chrome-extension state and must be rechecked at the time
of browser live testing.

## Root Entrypoints

The approved root Python files are recorded in
`logs/w4/cli_wrapper_candidates.txt`. Most are wrappers; the root keeps build,
gate, app, and engine entrypoints such as `local_ci.py`, `code_health.py`,
`scored_eval_suite.py`, `main.py`, `kampung_ai_app.py`, and
`build_kampung_ai_app.py`.

## Moved Tests

Ordinary smokes now live under `tests/smokes/`, replays under `tests/replays/`,
and eval helpers under `tests/evals/`. Prefer `local_ci.py` for the default
proof. When running individual old smoke commands, use the new path, for
example:

```bash
./venv/bin/python tests/smokes/browser_extension_bridge_smoke.py
./venv/bin/python tests/smokes/harness_agentic_deep_smoke.py
./venv/bin/python tests/smokes/context_window_canaries_smoke.py
```

Historical handoff docs may still show old root-level smoke paths because they
record the command used during that dated session. This runbook is the current
path source of truth.

## Code Health

`code_health.py` is package-aware, excludes `tests/`, and fails only new
over-300-line runtime violations. Pre-existing package debt is captured in
`logs/w4/grandfather_baseline.txt` and reported as W4 follow-up debt rather than
blocking this move.

The root count is ratcheted by `ROOT_PY_FILE_LIMIT` and should match the current
approved root entrypoint count.
