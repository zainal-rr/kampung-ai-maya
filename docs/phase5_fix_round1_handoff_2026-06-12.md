# Phase 5 Fix Round 1 — Handoff (2026-06-12)

Input: Zainal's live run (5 pass / 5 partial / 2 fail of 12; all three packs
activated in `skill_usage_events`). Diagnosis confirmed: retrieval layer works;
the failures were in the layers around it. Four root causes, four fixes, all
deterministic-smoke covered.

## Findings → root causes → fixes

### F1 — Banking `/complex` answer truncated mid-sentence (FAIL)

Root cause: hardcoded provider output caps in `models.py` — `TheMind` (GPT
plan lane) `max_output_tokens=1024`, `TheSteward` (Claude review) `max_tokens=1024`.
The banking plan + steward review exceeds 1024 tokens; the PROVIDER truncated,
not Telegram (delivery already chunks at 3900 chars per message).

Fix (`models.py`): caps are env-tunable with deep-lane defaults —
`MAYA_MIND_MAX_OUTPUT_TOKENS` (default 4096), `MAYA_STEWARD_MAX_TOKENS`
(default 2048). COST NOTE: /complex turns can now bill up to ~4× more output
tokens. Watch `/cost` after the retest; tune the env vars down if needed.

### F2 — "design the network for a new branch campus" hijacked by artifact router (FAIL)

Root cause: `resolve_semantic_artifact_intent` (Grok semantic router in
`artifact_semantic_resolver.py`) runs inside the document-action path before
domain knowledge has any say. `_candidate()` only filters questions starting
with what/why/how/where/tell me/explain — "design ..." reached Grok, which
classified it as an artifact ask and returned the Word/Excel/PPT clarify.

Fix (`artifact_semantic_resolver.py` + `domain_knowledge.py`): precedence gate
`domain_question_precedence(text)` runs FIRST in the resolver:

- diverts to the chat lane (returns None) only when BOTH: a STRONG domain-pack
  trigger matches (`strong_domain_skill_id`, veto-aware; weak matches never
  divert) AND no explicit artifact-format word is present.
- `_EXPLICIT_FORMAT_MARKERS` keeps the artifact path for: word/docx/document,
  excel/xlsx/sheet/spreadsheet/workbook/tracker/ledger, powerpoint/pptx/
  slides/deck/presentation, markdown/md/html/pdf/file, save/attach, and
  document-type deliverables (report, proposal, guide, manual, memo, letter,
  brief). So "make an Excel liquidity gap analysis" still builds a spreadsheet
  (Phase 4 contract) and "monthly budget tracker" still hits the budget lane.
- Gate reads `maya_skills/active/` (DEFAULT_SKILL_DIR) — it follows promotion
  state automatically.

### F3 — Partials: VRF missing verification/rollback; DCF point-value; cloud missing provider mapping + pricing caveat (3 PARTIALS)

Root cause: one shared cause — the injected context told the model to "ground
the answer and name the source" but never required recipe COMPLETENESS. The
model cited recipes and then dropped their mandatory sections.

Fix (`domain_knowledge.py`): the context tail is now a 4-point
"Domain answer contract": (1) name the source; (2) include every mandatory
recipe section — verification, rollback, sensitivity ranges, AWS/GCP/Azure
mappings, pricing/advice caveats, limitations — "dropping a mandatory recipe
section is a wrong answer"; (3) when the recipe requires a range, COMPUTE the
range values, never a point value or a deferred suggestion; (4) honesty
fallback unchanged. Rides every domain context including the sticky path.

### F4 — Finance follow-up answered without retrieval/citation (PARTIAL)

Root cause (two layers):
1. Trigger gap: the skill declared plural "preference shares"; the follow-up
   said "preference share issuance" (singular) — word-boundary match fails.
2. Structural: follow-up turns carry no domain memory; any follow-up worded
   without triggers loses the pack.

Fixes:
- `maya_skills/proposed/finance_credit_analysis.md`: instrument trigger now
  covers "preference share", "preference shares", "share issuance".
- Sticky follow-up (`skill_registry.py` + `domain_knowledge_context_for_skill`):
  when no pack matches AND the message reads like a follow-up (starts with
  now/and/also/then/next/ok/what about/how about/what if, or references
  it/that/this/its/the same), retry retrieval against the most recent
  `domain:*` skill from `skill_usage_events` (last 8 events). Fail-silent: no
  token overlap → nothing injected ("now remind me to call mom" stays clean).
  Sticky activations log with reason "domain knowledge retrieval (sticky
  follow-up)" so you can audit them.

## Files changed

| File | Change |
| --- | --- |
| `models.py` | env-tunable output caps (F1) |
| `artifact_semantic_resolver.py` | precedence gate + format markers (F2) |
| `domain_knowledge.py` | answer contract, `strong_domain_skill_id`, `domain_knowledge_context_for_skill` (F2/F3/F4) |
| `skill_registry.py` | sticky follow-up retrieval + helpers (F4) |
| `maya_skills/proposed/finance_credit_analysis.md` | singular/issuance triggers (F4) |
| `skill_domain_smoke.py` | trigger variants, sticky retrieval, contract presence; inert check made promotion-state-agnostic (it asserted the pre-promotion world) |
| `domain_router_precedence_smoke.py` | NEW: precedence gate, resolver bypass, artifact regressions, sticky helpers, cap de-hardcoding |

## Deployment on the iMac (IMPORTANT ORDER)

1. Pull/sync the repo.
2. RE-COPY the finance skill to active/ — the trigger fix lives in `proposed/`
   and your promoted copy predates it:
   `cp maya_skills/proposed/finance_credit_analysis.md maya_skills/active/`
   (re-copying all three is harmless).
3. Run `python3 skill_domain_smoke.py` and `python3 domain_router_precedence_smoke.py` — both must pass.
4. Restart Maya.

## Retest matrix (only the 7 non-passing rows)

| Original result | Prompt | Now expect |
| --- | --- | --- |
| FAIL | `/complex` banking case | Complete answer, ends with a proper closing, steward review present |
| FAIL | `design the network for a new branch campus` | Network-pack chat answer with citation; NO Word/Excel/PPT question |
| PARTIAL | VRF prompt | Config + VERIFICATION commands + ROLLBACK section |
| PARTIAL | investor follow-up (after banking case) | Citation of `preference_share_feasibility`; if direct match misses, sticky reason appears in skill_usage_events |
| PARTIAL | DCF prompt | Computed sensitivity RANGE (e.g. value at WACC±1%), not a point + suggestion |
| PARTIAL | three-tier on AWS | AWS/GCP/Azure mapping table/lines + pricing-verification caveat |
| PASS (re-verify) | `make me a monthly budget tracker` | Still the budget Excel lane (gate must not regress artifacts) |

Evidence query unchanged; sticky events visible via:
`SELECT skill_id, reason FROM skill_usage_events WHERE reason LIKE '%sticky%';`

## Honest limits of this round

- F3 is a PROMPT contract, not a hard gate — the model can still under-comply.
  If retest shows recipes cited-but-ignored again, the next escalation is a
  deterministic post-check (grep the draft for required sections and re-prompt
  once), same pattern as the PPTX governance loop.
- The sticky window is "last 8 usage events", not time-bound: a domain
  follow-up hours later can still re-inject. Tighten to a timestamp window if
  that annoys in practice.
- Zainal's run report/JSON were not in the mounted folders; this round worked
  from the chat summary. Drop them into the repo if anything above mismatches
  what you saw.
