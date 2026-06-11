# Kampung AI Validation Test Checklist — Session 2026-06-10

Run phases in order. Stop and investigate on any failure before continuing.
Companion document: `SESSION_CHANGE_REPORT.md`.

## Phase 0 — Preflight (before starting Maya)

- [ ] Review `SESSION_CHANGE_REPORT.md`, especially the concurrent-changes warning.
- [ ] Confirm `.env` contains `TELEGRAM_ALLOWED_CHAT_IDS=6429253538` (your chat id). Without it the bot will ignore you — this is the new closed-by-default security gate.
- [ ] Confirm `MAYA_AGENTIC_LOOP=0` for the first phases (turn it on only in Phase 6).
- [ ] `pip install -r requirements.txt` in the venv (new file; confirms it matches reality).
- [ ] Reconcile the concurrent session's changes (cost-lane refactor deleted `cost_spreadsheet.py`; new browser extension lane) — decide they are intended before testing on top of them.

## Phase 1 — Local CI / smokes on the iMac

- [ ] Run your full local CI (`python3 local_ci.py` or your usual entry).
- [ ] New smokes individually if CI does not include them yet:
  - [ ] `python3 document_species_smoke.py`
  - [ ] `python3 skill_domain_smoke.py`
  - [ ] `python3 harness_agentic_deep_smoke.py`
- [ ] Previously failing, now expected green: `pptx_visual_assets_smoke.py`, `pptx_rejected_delivery_smoke.py`, `pptx_rescue_flow_smoke.py`, `office_theme_smoke.py`.
- [ ] Sandbox-unverifiable, must pass here: `document_actions_smoke.py` (needs live xAI key), `word_simple_edit_smoke.py`.
- [ ] If any harness smoke stalls: check the browser extension bridge wait (concurrent change), test with `MAYA_BROWSER_EXTENSION_WAIT_SECONDS=0`.

## Phase 2 — Telegram security gate (live)

- [ ] Restart the Maya service; confirm Telegram replies normally from YOUR account.
- [x] From a second Telegram account (or a friend's): message the bot — it must stay silent, and the log must show "Rejected unauthorized Telegram chat". Evidence: second phone sent `/start`, `Hi`, and `Hello` at 2026-06-10 23:15 MYT; Maya stayed silent and `logs/launchd.stderr.log` recorded three `Rejected unauthorized Telegram chat 7090185710` warnings.
- [ ] Voice note, photo, and /command from your account all still work (allowlist covers all four handlers).

## Phase 3 — Memory honesty (live chat)

- [x] "Remember that my favorite airline is AirAsia" → then "what is my favorite airline?" → correct recall.
- [x] "Forget my favorite airline" → ask again → no leak. Evidence: final Telegram turn at 2026-06-10 15:52:04 UTC replied "I don't have that saved yet"; `canonical_memory_items.mem_d1614c842c2be171` is `forgotten`. Earlier attempts at 15:35 and 15:46 leaked AirAsia after a claimed forget, so keep this as a regression watch.
- [ ] Run the weekly memory flow (or wait for schedule) → confirm the forgotten fact does NOT come back (`/memory inspect`; audit shows `canonical_write_blocked_forgotten` if it tried).
- [ ] If you have >80 saved memories: recall an OLD one (pre-cliff bug would have lost it).

## Phase 4 — Document species (live generation, judge with your eyes)

- [x] Word: "make me a workshop plan for a school robotics day" → expect Learning Objectives / Session Schedule / Team Roles, NOT a findings report. Evidence: Telegram turn 5739 completed and sent `/Users/zainalabidinjamal/Desktop/Maya/documents/workshop-document-v5.docx`.
- [x] Word: "write a YouTube content strategy doc" → expect Audience / Pillars / Cadence / Metrics, NOT Goal/Workstreams. Evidence: Telegram turn 5740 completed and sent `/Users/zainalabidinjamal/Desktop/Maya/documents/youtube-document-v5.docx`.
- [x] Word: "make a nine day Kazakhstan itinerary" → must contain Day 1 through Day 9 headings (this was the false-pass case). Evidence: Telegram turn 5743 completed cleanly on 2026-06-10 18:22:05 UTC with `Done. I created a Word draft.` and sent `/Users/zainalabidinjamal/Desktop/Maya/documents/kazakhstan-itinerary-v3.docx`; direct `.docx` inspection confirmed `Day 1 Plan` through `Day 9 Plan`. `/review` turn 5744 showed Claude PASS for the same topic, and `qa_disagreement_events` was empty, so no false validator audit noise was created.
- [ ] Excel: "make a youtube tracker", "make an agriculture tracker", "make a coding sprint tracker" → three DIFFERENT column schemas.
- [ ] Excel: "make an Excel liquidity gap analysis for the institution" → Inflow/Outflow/Net/Cumulative columns with working gap + coverage-ratio formulas.
- [ ] Excel: "monthly budget tracker" and a travel budget → still use the original budget lanes (regression).
- [ ] PPTX: generate a teaching deck (school topic), a sprint review deck, an investor pitch deck, and "agriculture concern in Malaysia" → four different narrative arcs, four different closings, four different accent colors AND background tints; technical/architecture deck keeps the classic dark navy.
- [ ] The real test: do they FEEL bespoke now? Note anything still samey — that list drives the next iteration.

## Phase 5 — Domain knowledge packs

NOTE 2026-06-11: finance pack expanded (FMVA/CFA/CPA/CFP/CAIA/FRM breadth, 26 files)
and a third pack added: cloud solution architecture (AWS/GCP/Azure, 12 files).
Skill FILENAMES unchanged for finance — promote commands below are still correct.
Promote by COPY, not move (`skill_domain_smoke` reads from `proposed/`).

RUN 1 (2026-06-12): 5 pass / 5 partial / 2 fail — all three packs activated;
failures were in surrounding layers. FIX ROUND 1 shipped same day: output-cap
truncation, artifact-router precedence gate, domain answer contract, sticky
follow-up retrieval + singular triggers. Details + retest matrix:
`docs/phase5_fix_round1_handoff_2026-06-12.md`.

RETEST (2026-06-12, via Telegram text handler): 7/7 PASS after two iMac
hotfixes — `should_use_plan_path` tightened ("it plans to raise" no longer
hijacks /complex into plan mode) and provider-mapping rule added to the domain
answer contract. Both hotfixes now smoke-covered (`_plan_path_checks` in
`domain_router_precedence_smoke`, mapping-rule assert in `skill_domain_smoke`);
"make me a plan" regex gap also closed. Evidence:
`phase5-domain-pack-round1-retest-report-2026-06-12.md` (+ 2 JSONs, Downloads).

- [x] FINAL HUMAN ACCEPTANCE: 5/5 passed from live Telegram (2026-06-12).
  Evidence: banking `/complex` complete in ~82.7s with gap = 30m, coverage =
  0.50, cash-adjusted ROA, redemption risk, feasibility recipe cited; investor
  follow-up landed via sticky finance retrieval; VRF included config +
  verification + rollback; branch campus stayed with the network pack (no
  cloud/artifact hijack); three-tier AWS included the AWS/GCP/Azure mapping +
  cost caveat. All five activations confirmed in `skill_usage_events`. No
  Telegram delivery errors in this window (log-tail errors are Jun 10/11).

**PHASE 5: PASSED (2026-06-12).**

Known nuance (not a defect, logged for later): `/route` shows only the outer
model lane (e.g. `Gemini Flash text`, `GPT 5.5 medium`); domain-pack
activation is visible only in `skill_usage_events`. Optional improvement:
append `+ domain:<pack>` to the route line when retrieval fired, so one view
tells the whole story.

Core (unchanged):
- [ ] Promote `maya_skills/proposed/network_engineering.md` → `active/` (your normal flow).
- [ ] Promote `maya_skills/proposed/finance_credit_analysis.md` → `active/`.
- [ ] Promote `maya_skills/proposed/cloud_solution_architecture.md` → `active/` (NEW).
- [ ] Ask: "create a vrf for customer A on the PE router" → answer should cite the VRF recipe and include config + verification + rollback.
- [ ] Ask the full banking case (via `/complex`) → answer should cite finance recipes, show formulas (gap = 30, coverage = 0.50, cash-adjusted ROA), and flag the preference-share risks.
- [ ] Ask a follow-up: "now assess the preference share issuance from an investor's perspective" → fresh retrieval should cite the feasibility recipe.
- [ ] Ask "my home wifi keeps dropping" → must NOT inject networking recipes (veto).
- [ ] `/route` (or skill usage view) shows `domain:network_engineering` / `domain:finance_credit_analysis` / `domain:cloud_solution_architecture` activations.

Breadth (new, optional but recommended — one per new discipline):
- [ ] Finance: "build a DCF valuation for a company with 100m free cash flow growing 8%, WACC 10%" → cites `dcf_valuation`, shows PV math and a sensitivity range, never a single point value.
- [ ] Finance: "calculate the 99% value at risk on a 10 million portfolio with 2% daily volatility" → cites `value_at_risk`, shows the z×σ×value formula AND mentions expected shortfall.
- [ ] Finance: "am I on track to retire with 80k a year if I have 200k saved?" → cites `retirement_goal_planning`, computes the nest egg and gap, presents levers not a prescription.
- [ ] Cloud: "design a three-tier web app on AWS for an online store" → cites `three_tier_web_app`, gives AZ redundancy reasoning + AWS/GCP/Azure mapping, flags pricing as needing current verification.
- [ ] Cloud: "what disaster recovery setup do I need for an RTO of 15 minutes?" → cites `high_availability_dr`, lands on warm standby with the cost honesty note.
- [ ] Cross-domain guard: "design the network for a new branch campus" → routes to NETWORK pack (not cloud); "back up my photos to icloud" → no pack injects anything.
- [ ] Regression: "monthly budget tracker" still goes to the budget Excel lane (finance veto held after trigger broadening).

## Phase 6 — Agentic loop (live GPT planner)

DETAILED RUN SHEET (2026-06-12): `docs/phase6_agentic_loop_validation_2026-06-12.md`
— includes the loop trigger conditions (harness start markers!), exact prompts,
DB evidence queries, approval-gate both-ways test, budget/honesty test, cost
review, and the kill-switch drill. Commit the working tree before starting.

- [ ] Set `MAYA_AGENTIC_LOOP=1`, restart Maya.
- [ ] Give a multi-step request through the harness (e.g. "research X, then remember the key fact, then summarize"). Watch the trace for `loop_iteration`, `agentic_action`, `domain_knowledge` events.
- [ ] Confirm the loop STOPS: budget is 8 steps max; a run must never spin.
- [ ] Trigger an approval path (ask for something that sends a file) → run pauses for your yes/no; decline → honest cancellation.
- [ ] Check `/cost` for `gpt_harness_planner_calls` — confirm the planner cost is visible and acceptable.
- [ ] If anything misbehaves: set `MAYA_AGENTIC_LOOP=0` — default behavior returns instantly.

## Phase 7 — One week of honest field use

- [ ] Use Maya daily for real work; keep a running note of every output that feels generic, wrong-shaped, shallow, or mis-routed.
- [ ] Note every domain question you ask that has no pack (candidates for the next skill+docs tree — zero code needed).
- [ ] End of week: review the disappointment list — that, not a feature idea, decides the next build.

## Sign-off

- [ ] All phases green or consciously waived.
- [ ] Commit message-by-area, or one squash — but commit; the working tree is carrying two sessions of uncommitted work.
