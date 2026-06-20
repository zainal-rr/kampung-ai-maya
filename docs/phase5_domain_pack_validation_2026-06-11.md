# Phase 5 — Domain Knowledge Pack Validation (Detailed Run Sheet)

Date prepared: 2026-06-11. Companion: `KAMPUNG_AI_VALIDATION_TEST_CHECKLIST.md` (Phase 5 section).
Estimated time: 25–40 minutes (core), +20 minutes (full breadth).

## What Phase 5 proves

The domain knowledge layer (`domain_knowledge.py`) is deterministic lexical RAG:
skill files in `maya_skills/active/` declare trigger phrases and a docs tree;
matching prompts get recipe content injected into the model's context with
citations. The smokes already prove routing and retrieval deterministically.
What ONLY a live run can prove:

1. The MODEL actually grounds its answer in the retrieved recipe (uses its
   formulas/method) instead of free-styling past it.
2. The full Telegram → harness → retrieval → drafting → reply chain works
   end-to-end on the iMac.
3. Activations are recorded in the database for auditability.

## The three packs under test

| Pack | Skill file (filename = skill_id) | Docs tree | Size |
| --- | --- | --- | --- |
| Network engineering | `network_engineering.md` | `docs/networking/` | concepts + config recipes |
| Finance (broadened 2026-06-11: FMVA/CFA/CPA/CFP/CAIA/FRM) | `finance_credit_analysis.md` | `docs/finance/` | 26 files: 7 concepts, 18 recipes |
| Cloud solution architecture (NEW 2026-06-11: AWS/GCP/Azure) | `cloud_solution_architecture.md` | `docs/cloud/` | 12 files: 4 concepts, 7 recipes |

Finance kept its original FILENAME on purpose — promote commands and the
`domain:finance_credit_analysis` log id are unchanged from the original plan.

## Prerequisites (do not start without these)

- [ ] Phases 0–4 green (checklist shows 2, 3, and the three Phase 4 Word items already passed).
- [ ] `MAYA_AGENTIC_LOOP=0` in `.env` — Phase 6 tests the loop separately; keep variables isolated.
- [ ] `TELEGRAM_ALLOWED_CHAT_IDS=6429253538` still set.
- [ ] Latest code pulled/present on the iMac including `docs/cloud/`, the expanded `docs/finance/`, and the updated `skill_domain_smoke.py`.
- [ ] `python3 skill_domain_smoke.py` passes on the iMac (proves parsing/routing on THIS machine before going live).

## Step 1 — Promote the skills (COPY, never move)

```bash
cd ~/projects/kampung-ai
cp maya_skills/proposed/network_engineering.md        maya_skills/active/
cp maya_skills/proposed/finance_credit_analysis.md    maya_skills/active/
cp maya_skills/proposed/cloud_solution_architecture.md maya_skills/active/
```

WHY copy: `skill_domain_smoke.py` reads from `proposed/`. Moving the files
breaks the smoke for every future session. The duplicate is intentional;
`proposed/` is the source of truth for the smoke, `active/` is what live
retrieval scans.

## Step 2 — Sanity check loading (before restart)

```bash
python3 -c "
from domain_knowledge import load_domain_skills, DEFAULT_SKILL_DIR
skills = load_domain_skills(DEFAULT_SKILL_DIR)
for s in skills:
    print(f'{s.skill_id:32s} -> {s.kb_root}  strong={len(s.strong_triggers)} weak={len(s.weak_triggers)} vetoes={len(s.non_triggers)}')
assert {s.skill_id for s in skills} >= {'network_engineering','finance_credit_analysis','cloud_solution_architecture'}, 'MISSING PACK'
print('OK: all three packs load from active/')
"
```

Expected: three lines + `OK`. If a pack is missing, the parser rejected the
skill file — check that the file has a `## Knowledge Base` section containing a
backticked `docs/<name>/` path that EXISTS as a directory, and a
`## Trigger Phrases` section. Fix before continuing. Do NOT test on a
half-loaded set; routing results would be meaningless.

## Step 3 — Restart Maya

Your normal launchd restart. Then confirm in the log that exactly ONE poller
is running (the fcntl lock from the intake fix should guarantee it) and send a
plain `hello` from your phone to confirm normal chat works before testing.

## Step 4 — Live test matrix

Send each prompt as a normal Telegram message (except #2 which uses `/complex`).
For each: record PASS/FAIL and paste/screenshot the cited source line.

### Core (required)

| # | Prompt | Must route to | Expected in the answer | Instant-fail signals |
| --- | --- | --- | --- | --- |
| 1 | `create a vrf for customer A on the PE router` | network | Cites the VRF recipe; config block + verification commands + ROLLBACK section | No citation; config without rollback |
| 2 | `/complex` + full banking case (below) | finance | Cites liquidity/RR/ROA recipes; computes gap = 30m, coverage = 0.50, cash-adjusted ROA; flags preference-share risks; "not professional financial advice" note | Numbers asserted without formulas; no recipe named |
| 3 | `now assess the preference share issuance from an investor's perspective` | finance | Fresh retrieval citing `preference_share_feasibility` | Reuses turn-2 text without new citation |
| 4 | `my home wifi keeps dropping` | NONE (veto) | Normal helpful answer, zero recipe injection | Any `docs/networking` citation |
| 5 | `make me a monthly budget tracker` | NONE (veto) | Routes to the budget Excel lane (regression guard: finance triggers were broadened today; this veto must still hold) | Finance pack activates |

Banking case text for #2:

```
A non-deposit financial institution reports a loan book of 200 million and a
stable ROA of 7%, with 60% of exposures restructured and extended. Quantify
the liquidity gap given near-term obligations of 60 million and expected
inflows of 30 million, and evaluate the institution's ability to meet
near-term obligations. Assess the feasibility of the proposed Preference
Share issuance.
```

### Breadth (recommended; minimum = #6 and #9)

| # | Prompt | Must route to | Expected recipe + markers |
| --- | --- | --- | --- |
| 6 | `build a DCF valuation for a company with 100m free cash flow growing 8%, WACC 10%` | finance | `valuation/dcf_valuation`; PV-by-year math, terminal value, equity bridge, a SENSITIVITY RANGE — a single point value is a FAIL |
| 7 | `calculate the 99% value at risk on a 10 million portfolio with 2% daily volatility` | finance | `risk/value_at_risk`; shows value × 2.33 × σ (≈466k), states VaR is a threshold not a worst case, mentions expected shortfall |
| 8 | `am I on track to retire with 80k a year if I have 200k saved and save 2k a month?` | finance | `planning/retirement_goal_planning`; nest egg = spending/withdrawal rate, FV math, gap + levers (not a prescription); planning-not-advice note |
| 9 | `design a three-tier web app on AWS for an online store` | cloud | `architecture/three_tier_web_app`; ≥2 AZ reasoning, LB-only ingress, private DB, AWS/GCP/Azure mapping, pricing flagged for verification |
| 10 | `what disaster recovery setup do I need for an RTO of 15 minutes?` | cloud | `resilience/high_availability_dr`; tier ladder, lands on warm standby, cost honesty + "test the failover" |
| 11 | `design the network for a new branch campus` | network (COLLISION GUARD) | Network pack answers — if cloud answers this, trigger weights collided: report immediately |
| 12 | `back up my photos to icloud` | NONE (veto) | Normal answer, no cloud pack injection |

## Step 5 — Evidence collection

```bash
sqlite3 session_history.db \
  "SELECT skill_id, count(*) FROM skill_usage_events
   WHERE skill_id LIKE 'domain:%' GROUP BY skill_id;"
```

Expected after the full matrix: all three `domain:` ids with plausible counts
(network ≥2, finance ≥3, cloud ≥2). Also useful: `/route` in Telegram, and the
launchd log for any retrieval errors.

## Failure triage

| Symptom | Likely cause | Where to look |
| --- | --- | --- |
| Pack never activates | Skill file parse failure or trigger mismatch | Step 2 output; trigger phrases vs your exact wording |
| Wrong pack answers (esp. #11) | Trigger collision / weak-trigger overlap | `detect_domain_skill` scoring; report the exact prompt |
| Answer cites recipe but ignores its method | Drafting problem, NOT retrieval | Same class as the Excel prose-in-cells fix; needs a drafting contract, report with screenshot |
| Citation missing but method correct | Prompt-context formatting | `domain_knowledge_context` output for that prompt |
| Veto prompts inject recipes | Veto phrase mismatch | `non_triggers` in Step 2; exact wording matters (substring match) |
| DB query returns nothing | Usage-event wiring, not retrieval | `skill_store.py` / harness event recording |

Any FAIL: stop, save the prompt + full reply + log lines, continue with the
rest of the matrix (failures are independent), report everything at the end.

## Rollback

```bash
rm maya_skills/active/network_engineering.md \
   maya_skills/active/finance_credit_analysis.md \
   maya_skills/active/cloud_solution_architecture.md
```

Restart Maya. Retrieval is silent again; `proposed/` copies are untouched.

## Sign-off bar

- [ ] All 5 core rows PASS.
- [ ] At least breadth #6 and #9 PASS.
- [ ] #11 routes to network (collision guard).
- [ ] Evidence query shows all three domain ids.
- [ ] Every cited number in finance answers traceable to a shown formula.
- [ ] Anything that felt shallow/wrong noted for the disappointment list (Phase 7 input).

## Phase map for orientation

Phases 0–7 (8 total): 0 Preflight · 1 Smokes · 2 Telegram security gate ·
3 Memory honesty · 4 Document species · 5 THIS — domain packs ·
6 Agentic loop (`MAYA_AGENTIC_LOOP=1`, separate night) · 7 One week of honest
field use → disappointment list drives the next build.
