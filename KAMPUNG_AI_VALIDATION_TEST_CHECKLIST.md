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

- [ ] Promote `maya_skills/proposed/network_engineering.md` → `active/` (your normal flow).
- [ ] Promote `maya_skills/proposed/finance_credit_analysis.md` → `active/`.
- [ ] Ask: "create a vrf for customer A on the PE router" → answer should cite the VRF recipe and include config + verification + rollback.
- [ ] Ask the full banking case (via `/complex`) → answer should cite finance recipes, show formulas (gap = 30, coverage = 0.50, cash-adjusted ROA), and flag the preference-share risks.
- [ ] Ask a follow-up: "now assess the preference share issuance from an investor's perspective" → fresh retrieval should cite the feasibility recipe.
- [ ] Ask "my home wifi keeps dropping" → must NOT inject networking recipes (veto).
- [ ] `/route` (or skill usage view) shows `domain:network_engineering` / `domain:finance_credit_analysis` activations.

## Phase 6 — Agentic loop (live GPT planner)

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
