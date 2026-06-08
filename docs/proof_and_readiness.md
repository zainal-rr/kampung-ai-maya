# Kampung AI Proof And Readiness

This document separates deterministic software proof from live operational proof. Passing local tests means the code path is healthy. It does not automatically prove physical voice, browser field reliability, hardware, billing behavior, or long-term daily reliability.

## Current Conservative Scores

| Area | Current estimate | Why it is not higher yet |
| --- | ---: | --- |
| Telegram | 92% | Text, voice-note routing, image input, memory, and document workflows are strong; real daily soak still matters |
| Document creation | 90% | Word/Excel/PPTX quality gates are much stronger; PowerPoint and broad edit workflows still need more human-quality sampling |
| Memory architecture | 85% | Canonical save/recall/forget and weekly path exist; long-term behavior needs real time proof |
| Weekly memory automation | 85% | Manual/live status and dry runs exist; unattended scheduled execution needs observation |
| Browser/agent workflow | 78-80% | Search/read/click/capture/safety proof exists; exact site manipulation and recovery need more field runs |
| Agentic workflow | 78% | `/complex` planning and approval gates exist; checkpointed execution needs more end-to-end workflows |
| Hardware/Blender/Maker | 65-70% | Maker software path exists; printer, Omi, and Mudra need physical proof |
| Overall Kampung AI | 82-84% | Strong personal prototype with real harness shape; not yet 30-day operational proof |

## Deterministic Proof

These checks run without relying on live provider calls by default:

```bash
./venv/bin/python local_ci.py
```

Current local CI coverage includes:

1. Python compile checks.
2. Blocking code health.
3. Scored eval suite.
4. Document request parser.
5. Natural artifact parser.
6. Artifact clarification/session continuity.
7. Artifact naming and delivery gate.
8. Artifact retry loop.
9. Office edit workflow.
10. Word technical repair.
11. Semantic Telegram fresh 500.
12. Voice document transcript.
13. Voice artifact transcript replay 500.
14. Voice Telegram transcript replay 10000.
15. Canonical memory.
16. Telegram text/voice/photo input.
17. Browser semantic scrape 500.
18. Retired architecture guard.
19. Memory perspective.
20. Hardening audit.
21. Latest demo evidence.

## Live Browser Proof

The live browser probe is separate from CI:

```bash
./venv/bin/python browser_multistep_live_probe.py
```

It currently covers:

1. Booking.com search pages.
2. Booking.com listing/detail clicks.
3. Google hotel review lookup.
4. Airbnb search pages.
5. Airbnb listing/detail clicks.
6. Airbnb guest-review evidence checks.
7. YouTube search.
8. YouTube video open.
9. Excel capture of live options.
10. Safety stops before booking, payment, upload, private identifiers, and OTP.

Latest run: 50/50 passed.

Known browser weakness:

1. Exact property-name extraction for review enrichment still needs improvement.
2. Real filter manipulation needs more field testing.
3. Popup/login-wall recovery needs more field evidence.
4. Screenshots/DOM evidence should be captured more consistently for final audit logs.

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
5. Memory self-heal dry run is prepared.

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
