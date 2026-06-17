# Kampung AI Proof And Readiness

This document separates deterministic software proof from live operational proof. Passing local tests means the code path is healthy. It does not automatically prove physical voice, browser field reliability, hardware, billing behavior, or long-term daily reliability.

## Current Conservative Scores

| Area | Current estimate | Why it is not higher yet |
| --- | ---: | --- |
| Telegram | 92% | Text, voice-note routing, image input, memory, and document workflows are strong; real daily soak still matters |
| Document creation | 90% | Word/Excel/PPTX quality gates are much stronger; PowerPoint and broad edit workflows still need more human-quality sampling |
| Memory architecture | 85% | Canonical save/recall/forget and weekly path exist; long-term behavior needs real time proof |
| Weekly memory automation | 85% | Manual/live status and dry runs exist; unattended scheduled execution needs observation |
| Browser/agent workflow | 90-92% | Two consecutive live Chrome reliability nights passed the strong threshold; remaining partials are open-rank/result-grounding refinements, not safety or critical failures |
| Agentic workflow | 78% | `/complex` planning and approval gates exist; checkpointed execution needs more end-to-end workflows |
| Hardware/Blender/Maker | 65-70% | Maker software path exists; printer, Omi, and Mudra need physical proof |
| Overall Kampung AI | 84-86% | Strong personal prototype with real harness shape and browser proof now above the strong threshold; not yet 30-day operational proof |

## Deterministic Proof

These checks run without relying on live provider calls by default:

```bash
./venv/bin/python local_ci.py
```

Default local CI is the fast edit-loop gate. It includes representative
canaries for the scored eval suite, artifact-continuity matrices, and large
replay banks. The full scored eval suite, full artifact matrices, and full
500/10k deterministic replays run in the extended tier:

```bash
./venv/bin/python local_ci.py --extended
```

Run `--extended` before merge/release and from the optional nightly CI launchd
job. Live provider checks remain explicit:

```bash
./venv/bin/python local_ci.py --live-providers
```

Current fast local CI coverage includes:

1. Python compile checks.
2. Blocking code health.
3. Scored eval suite representative canary.
4. Document request parser.
5. Natural artifact parser.
6. Artifact clarification/session continuity representative canaries.
7. Artifact naming and delivery gate.
8. Artifact retry loop.
9. Office edit workflow.
10. Word technical repair.
11. Semantic Telegram fresh representative canary.
12. Voice document transcript.
13. Voice artifact transcript representative canary.
14. Voice Telegram transcript representative canary.
15. Canonical memory.
16. Telegram text/voice/photo input.
17. Browser semantic scrape representative canary.
18. Retired architecture guard.
19. Memory perspective.
20. Hardening audit.
21. Latest demo evidence.

Extended CI adds the full scored eval suite, full artifact
clarification/session continuity matrices, full semantic Telegram 500, voice
artifact 500, voice Telegram 10000, browser semantic scrape 500, memory recall
compare, and deeper agentic/flight reliability checks. This keeps subtle
full-replay regressions out of the hot edit loop while preserving the
pre-merge/nightly safety net.

## Live Browser Proof

The browser reliability harness runs the full prompt bank (6 work lanes x 10
prompts + 10 safety prompts) through Maya's real `run_browser_capability`
path and records an 8-field evidence record per run: request, parsed intent,
browser steps, final page state, extracted answer, safety boundary,
screenshots + page text, and a pass/partial/fail label.

```bash
# routing + parsing proof, no browser (also gated in CI):
./venv/bin/python live_browser_reliability_run.py --dry-run --lane all

# live night on the iMac (resumable with the same --night-id):
./venv/bin/python live_browser_reliability_run.py --lane all --night-id night1

# one lane at a time:
./venv/bin/python live_browser_reliability_run.py --lane flights --night-id night1
```

Live browser proof runs default to the Maya Chrome extension driver. A counted
browser night must open work tabs inside the `Maya` Chrome tab group unless the
run is explicitly marked as an AppleScript legacy baseline.

Evidence lands in `logs/live_tests/reliability/<night_id>/` (runs.jsonl,
night.md, shots/). After a live night, lane results are bridged automatically
into `browser_benchmark.py` live scores and `live_test_evidence.py`.

Validators enforce: correct routing, parsed-intent match, no stale-context
reuse (the Osaka case), no Explore-instead-of-Search, grounding of every
quoted price in the final page text (anti-hallucination), honest answers on
blocked or empty pages, clarification questions instead of guessed defaults,
and zero browser actions after a safety stop.

Live targets for calling browser automation strong: >=85% completion, 100%
safety stops, zero stale-context/hallucination/honesty criticals.

The older `browser_multistep_live_probe.py` remains as a URL-level page probe,
but the reliability harness is the primary live proof because it exercises
Maya's own skill execution path end to end.

Latest live evidence:

1. `night2` passed the strong browser target with 95% completion, 10/10 safety stops, and zero stale-context, hallucination, honesty, or safety criticals.
2. `night3-rerun` passed the strong browser target with 91.7% completion, 10/10 safety stops, and zero stale-context, hallucination, honesty, or safety criticals.
3. `night4_extension_rerun` passed the strong browser target with 96.7% completion, 10/10 safety stops, and zero stale-context, hallucination, honesty, or safety criticals.
4. `night4_extension_rerun` lane detail: flights 9/10 plus one partial, stays 10/10, safety 10/10, Google Search 9/10 plus one partial, Google Images 10/10, YouTube 10/10, Reddit 10/10.
5. `night4_extension_rerun` audited 58 browser-opening steps with zero non-extension `open_url` operations, so counted browser proof now requires the Maya Chrome extension path and `Maya` tab group.
6. The original `night3` attempt is not counted because extension tab cleanup exposed a Chrome window lifecycle bug; the bug was fixed and the clean rerun is recorded separately as `night3-rerun`.

Known browser weakness:

1. Exact property-name extraction for review enrichment still needs improvement.
2. Real filter manipulation needs more field testing.
3. Popup/login-wall recovery needs more field evidence (the harness now
   detects blocked pages, and Reddit search falls back to old.reddit.com).
4. Open-rank followups (`open the first video/thread`, `open the second result`) can still be partial when no prior on-screen options survive cleanup.
5. Some image/video result pages need stronger grounding extraction when only 4/5 visible options are recovered from page text.

## Retired Architecture Guard

The old alternate coding-provider architecture and deep-routing path have been removed from active code. `legacy_architecture_removed_smoke.py` scans active files and fails local CI if retired markers return.

This is important because having two competing harness stories causes routing confusion, false progress claims, and maintenance drift.

## Document Quality Proof

Current document proof is strong in deterministic tests and Telegram/iMac observed use:

1. Word has local `.docx` parse validation, visual QA, scenario checks, and review.
2. Excel has formula, domain-row, formatting, and usefulness checks.
3. PowerPoint has rendering, notes, dark-theme default, visual review, and repair behavior.
4. Latest-document continuity works across created artifacts and edits.
5. Rejected artifacts should not be called final.

Remaining work for 95% document confidence:

1. More human-rated PowerPoint samples.
2. More non-travel Excel scenarios.
3. More long editing sessions against the same artifact.
4. More iMac-native open/focus/edit tests.

## Memory Proof

Current proof:

1. Canonical save/recall/forget tests pass.
2. Temporary test memory is separated from durable memory.
3. Forget no-leak behavior is covered.
4. Weekly dry/live status path exists.
5. Weekly reviewer fallback is covered: Claude review failure now saves a conservative summary, saves no unreviewed canonical facts, and audits the warning.
6. Memory self-heal dry run is prepared.

Remaining proof:

1. Unattended weekly run observation.
2. Seven-day reliability soak.
3. Thirty-day memory scorecard.
4. Real Omi transcript ingestion.
5. Confirmation that weekly memory never recreates forgotten facts over time.

## Voice Proof

Current proof:

1. Post-STT Telegram voice transcript routing has broad deterministic coverage.
2. Noisy transcript handling is tested.
3. Parked voice handoff is simulated and covered.
4. Grok voice is not allowed to perform long work itself.

Remaining proof:

1. Real iMac microphone.
2. xAI realtime websocket session.
3. Ara spoken output on the iMac.
4. Paid-session open/close duration.
5. Live park/resume behavior over 30 voice tasks.

## Hardware And Maker Proof

Current proof:

1. Maker workflow can create local source/export-style artifacts.
2. Print-safety boundaries are documented.
3. Maya stops before slicing, upload, or physical print without approval.

Remaining proof:

1. Real Blender/MCP live workflow.
2. Real mesh sanity checks against generated geometry.
3. Real Bambu slicing/upload boundary.
4. Physical print result.
5. Omi transcript flow.
6. Mudra event flow and gesture mapping.

## Public Proof Rules

Public proof can include:

1. README.
2. Public architecture document.
3. Latest demo summary.
4. Latest eval summary.
5. Maya Desk output after redaction.

Public proof must not include:

1. API keys.
2. Tokens.
3. Private keys.
4. OTPs.
5. Bank/card data.
6. Raw personal memory.
7. Unnecessary private local paths.
8. Credential-shaped live test strings.

## Next Reliability Target

To move toward 9/10:

1. Run a seven-day normal-use reliability soak.
2. Run a thirty-day reliability scorecard.
3. Record 50+ real browser field workflows.
4. Record 30 real iMac voice tasks.
5. Validate Omi and Mudra with physical hardware.
6. Validate Blender/Maker with actual print-boundary tests.
7. Keep local CI blocking and green after each architecture change.
