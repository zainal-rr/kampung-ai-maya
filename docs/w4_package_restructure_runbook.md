# W4 Package Boundary Restructure Runbook

Current as of 2026-06-17.

## Status

W4 moves runtime implementation out of the repository root and keeps the daily
operator commands at the root as real CLI wrappers. Waves 1 through 6 are built:
smokes/replays/evals now live under `tests/`, runtime modules live under
packages, and preserved root commands execute package entrypoints with
`runpy.run_module(..., run_name="__main__")` or their own `main()`.

Wave 6 app/import verification is green, and final `local_ci.py` passed 63/63
with zero blocking failures. Final acceptance still requires a clean committed
worktree. Independent reviews are complete with one operational risk carried
forward: the browser wrapper path is verified, but `client_connected` in
`browser_extension_bridge.py --status` is volatile live Chrome-extension state
and can be disconnected even when the packaged command path is correct.

## Current Proof Commands

Run these from the repo root:

```bash
./venv/bin/python local_ci.py
./venv/bin/python code_health.py
./venv/bin/python browser_extension_bridge.py --status
python -c "import kampung_ai_app"
```

`browser_extension_bridge.py --status` is query-only. A successful wrapper proof
means the command reaches the packaged bridge status code. For live browser
testing, require `owner_kind=engine` and `client_connected=true`; if it reports
`client_disconnected`, reload/reconnect the Chrome extension before testing.
The final W4 status snapshot is stored in `logs/w4/final_browser_status.txt`.

## Root Entrypoints

The approved root Python files are recorded in
`logs/w4/cli_wrapper_candidates.txt`. Most are wrappers; the root keeps build,
gate, app, and engine entrypoints such as `local_ci.py`,
`scored_eval_suite.py`, `main.py`, `kampung_ai_app.py`, and
`build_kampung_ai_app.py`. `code_health.py` is a root wrapper over
`maya_core.code_health`.

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

`code_health.py` runs the packaged `maya_core.code_health` implementation. It is
package-aware, excludes `tests/`, and fails only new over-300-line runtime
violations. Pre-existing package debt is captured in
`logs/w4/grandfather_baseline.txt` and reported as W4 follow-up debt rather than
blocking this move.

The root count is ratcheted by `ROOT_PY_FILE_LIMIT` and should match the current
approved root entrypoint count.
