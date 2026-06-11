# Chrome Extension Reliability Proof — 2026-06-11

## Summary

The browser reliability runner now fails before executing prompts when `--driver extension` is requested but the Maya Chrome extension is not connected to the local bridge. After connecting the extension and fixing the remaining active-context leak, the extension driver passed a full live browser reliability run.

This is intentional:

- extension proof runs must not silently fall back to AppleScript
- failed extension setup should be one clear blocker, not ten noisy lane failures
- no ungrouped Chrome tabs should be created during an extension-only test

## Initial Blocker

```bash
MAYA_BROWSER_EXTENSION_WAIT_SECONDS=0 \
  ./venv/bin/python live_browser_reliability_run.py \
  --mini \
  --night-id w6_preflight_check_20260611 \
  --driver extension \
  --no-screenshots \
  --settle-seconds 0
```

## Result

The runner stopped immediately:

```text
Chrome extension preflight failed: the Maya browser extension is not connected.
status: {'started': False, 'connected': False, 'port': 0}
```

This means W6 extension reliability is **blocked by extension connection**, not by AppleScript fallback or browser-skill routing.

## Follow-up Finding

After connecting the extension, the mini-night passed, but the full run initially froze before recording the first case. Sampling the process showed the live browser runner was waiting on a worker thread blocked in a raw file/subprocess read.

Root cause:

- Browser control itself was using the Chrome extension.
- Flight and stay skills still called `ActiveContextInspector` before parsing every travel request.
- `ActiveContextInspector` uses the macOS `OSBridge` path to ask for the frontmost app/page context.
- That meant explicit browser requests such as `find flights to Penang on June 24` could still touch AppleScript before the extension did any browser work.

Fix:

- `flight_search_skill.py` and `stay_booking_skill.py` now parse explicit requests without active-context inspection when the browser driver is `extension`.
- Active-context inspection remains available only when the user wording explicitly references the current trip/page, such as `this trip`, `this itinerary`, or equivalent trip-reference wording.
- Regression smoke added: `browser_extension_context_skip_smoke.py`.

## Live Proof Commands

```bash
PYTHONUNBUFFERED=1 MAYA_BROWSER_DRIVER=extension \
  ./venv/bin/python live_browser_reliability_run.py \
  --mini \
  --night-id w6_extension_mini_after_context_fix_20260611 \
  --driver extension \
  --no-screenshots \
  --settle-seconds 1

PYTHONUNBUFFERED=1 MAYA_BROWSER_DRIVER=extension \
  ./venv/bin/python live_browser_reliability_run.py \
  --lane all \
  --night-id w6_extension_full_after_context_fix_20260611 \
  --driver extension \
  --no-screenshots \
  --settle-seconds 1
```

## Result

Mini-night:

- completion: 88.9%
- safety stops: 1/1
- criticals: 0
- benchmark bridge: overall `browser_field_workflows: passed`
- only partial: `google_search-02`, validator could not verify opened result label in page text

Full run:

- completion: 96.7%
- safety stops: 10/10
- stale-context criticals: 0
- hallucination criticals: 0
- honesty criticals: 0
- safety criticals: 0

Lane breakdown:

- flights: 9 pass / 1 partial / 0 fail
- stays: 10 pass / 0 partial / 0 fail
- google_search: 9 pass / 1 partial / 0 fail
- google_images: 10 pass / 0 partial / 0 fail
- youtube: 10 pass / 0 partial / 0 fail
- reddit: 10 pass / 0 partial / 0 fail
- safety: 10 pass / 0 partial / 0 fail

Benchmark bridge:

- flights: passed
- google_images: passed
- google_search: passed
- reddit: passed
- safety: passed
- stays: passed
- youtube: passed
- overall `browser_field_workflows: passed`

Artifacts:

- `logs/live_tests/reliability/w6_extension_mini_after_context_fix_20260611/runs.jsonl`
- `logs/live_tests/reliability/w6_extension_full_after_context_fix_20260611/runs.jsonl`
- `logs/live_tests/reliability/w6_extension_full_after_context_fix_20260611/night.md`

## Acceptance Check

- every tab remains inside the Maya Chrome tab group
- cleanup after each non-safety case reported `CLOSED_EXTENSION_TABS` or `NO_EXTENSION_TABS`
- explicit flight/stay prompts no longer pre-read active context through AppleScript
- no unexpected AppleScript fallback in the normal extension path
- safety remains 100%

W6 is considered closed for current use, with AppleScript retained only as explicit legacy fallback.
