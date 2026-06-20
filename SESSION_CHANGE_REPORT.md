# Session Change Report — Claude (Cowork), 2026-06-10

Everything changed in this session, grouped by purpose, with files, behavior
changes, and verification status. Recheck against this list, then run
`KAMPUNG_AI_VALIDATION_TEST_CHECKLIST.md`.

## Read This First: Concurrent Changes Warning

While this session ran, **another session was also modifying the repo**
(browser extension lane: `browser_driver.py`, `browser_extension_bridge.py`,
`chrome_extension/`; agentic validators; and a cost-lane refactor that
**deleted `cost_spreadsheet.py` / `kampung_ai_cost_rows`**). Those changes are
NOT mine and are not documented here. I verified my changes still work with
them (12/12 marker spot-checks intact, smokes green against the merged tree),
but review that work separately before committing everything together.

---

## 1. Security & Correctness Fixes (the original 13-change review)

| Change | Files | What changed |
| --- | --- | --- |
| Telegram sender allowlist (CRITICAL) | `telegram_channel.py`, `.env`, `.env.example` | Closed-by-default `TELEGRAM_ALLOWED_CHAT_IDS` gate on every handler. Your chat id (6429253538, from your own preferences DB) added to `.env` so the bot keeps working. |
| Dead context commands bug | `assistant.py` | Indentation bug at the old line 183 unconditionally wiped `handle_context_command` results. Fixed; context commands can answer again. |
| Router chat hijack | `harness_router.py` | Bare verbs ("type ", "open ", "press ", "google") now only trigger at message start via `START_COMMAND_RE`; "what type of pasta" no longer starts a workflow. Also `_thread_id` dead params removed. |
| Memory recall cliff | `canonical_memory.py` | Removed `LIMIT 80` from recall/leak queries; added status index. Facts beyond 80 rows are recallable again. |
| Forgotten-memory resurrection | `canonical_memory.py`, `weekly_memory_live.py`, `omi_context_sieve.py`, `memory_audit.py` | `allow_resurrect=False` for derived writers (weekly, Omi); blocked writes audited as `canonical_write_blocked_forgotten`; pinned never silently unpinned (`MAX(pinned, excluded.pinned)`). |
| Permission policy miscalibration | `maya_permission_kernel.py`, `permission_policy.py` | Kernel feeds human-readable arg text (not JSON) to the policy; card detection is Luhn-validated (timestamps no longer flagged); bare "token"/"secret" markers tightened to real phrases. |
| Voice-reply dead branch | `telegram_channel.py` | `_should_send_voice` simplified; same behavior, honest code. |
| Init-once DB setup | `canonical_memory.py` | `CREATE TABLE`/`ALTER` no longer run on every memory call. |
| Fail-fast on missing keys | `assistant.py` | Missing `GOOGLE_API_KEY` logs a loud warning ("dummy" silent fallback removed); `main.py` already enforced require_env at startup. |
| .env priority | `config.py` | `load_dotenv(override=False)`: real environment variables now win over `.env`. |
| requirements.txt | `requirements.txt` (new) | pip-installable dependency list matching `dependency_manifest.json`. |
| Live batch false-pass | `imac_document_creation_batch_live.py` | Word docs can no longer pass live QA on word count alone; `local.passed` required. |
| Smoke updates forced by the above | `route_no_overwrite_smoke.py`, `telegram_voice_reply_policy_smoke.py` | Fake chats authorized via the new allowlist env. |

## 2. Agentic Loop (level 2 → level 4 scaffolding)

| Change | Files | What changed |
| --- | --- | --- |
| Loop edge + budget | `harness_graph.py`, `harness_state.py` | `verify → plan` conditional edge, `MAX_STEPS=8` budget, opt-in via `agentic_loop` state flag. Default single-pass behavior byte-identical. |
| Planner module | `harness_llm_planner.py` (new) | `plan_with_llm`, `choose_next_action` (tool pick or done), `verify_goal` — provider-agnostic `prompt -> str` hook, JSON-fence tolerant, degrade-to-single-pass on any failure. |
| GPT lane wiring | `assistant_model_lanes.py`, `harness_router.py`, `assistant.py` | `build_harness_planner()` exposes the GPT lane (None without `OPENAI_API_KEY`; usage logged as `gpt_harness_planner_calls`). Activation gated by `MAYA_AGENTIC_LOOP=1` (default 0, in `.env.example`). |
| **Loop deepening (this round)** | `harness_graph.py`, `harness_llm_planner.py`, `harness_state.py` | The executor now CONSUMES the planner's tool choice: permission-kernel check first (deny → honest refusal recorded; confirm → existing approval gate pauses the run), `memory.write` executes inline, browser/screen/document tools remap to the matching workflow executor, unknown tools fall back safely. Domain knowledge is re-retrieved **per loop step** (`domain_knowledge` trace event), so multi-part goals pull the right recipe per step. New trace events: `agentic_action`, `agentic_remap`, `tool_denied`, `approval_required`, `loop_iteration`. |
| Smoke | `harness_agentic_deep_smoke.py` (new) | Deterministic scripted planner proves: tool → loop → done (2 passes, memory actually written), approval pause on `telegram.send_file`, deny on sensitive file content. |

## 3. Portability & Hygiene

| Change | Files |
| --- | --- |
| Hardcoded `/Users/zainalabidinjamal/...` paths removed | `voice.py` (repo-relative logs), `sieve.py` (env-driven), `demo_evidence.py` (`Path.home()`) |
| Python 3.10 floor restored | `document_style.py` (nested async comprehension → loop) |
| Skill folder hygiene | `maya_skills/active/fake.md` → `disabled/`; DB skill "Can you update that to 4 days" → status `rejected` |

## 4. Document Species & Deck Visual Identity

| Change | Files | What changed |
| --- | --- | --- |
| Word species | `word_quality.py`, `word_quality_travel.py` | +5 species: workshop_plan, sop, investor_brief, strategy (+ detection order fixes); travel itineraries require Day 1..N headings for 2-12 days and are validated against them. |
| Excel species | `excel_species.py` (new), `office_drafter.py`, `document_actions_content_helpers.py` | 10 schema archetypes incl. dev_tracker and **financial_model** (Inflow/Outflow/Net/Cumulative + gap and coverage-ratio formula rows). Money lanes guarded; "roa"/"npl" substring traps avoided (multiword markers only). |
| Deck narrative arcs | `office_drafter_deck_scenarios.py`, `office_drafter_powerpoint.py`, `deck_species.py` (new) | +4 arcs (teaching, review, pitch, issue/awareness) with distinct closings; shared `detect_deck_species` single source of truth; topic-keyed general closings (no universal "Make The Recommendation Clear"). |
| Deck visual identity | `office_pptx_palette.py` (new), `office_pptx_layout.py`, `office_modern_files.py` | Species accent systems AND species-tinted backgrounds/panels/cards (dark family: green-black teaching, plum-black review, teal-black issue...; pastel family: tinted creams). Contrast bounds enforced (dark <80, pastel >200 channel). technical/general keep original 12161C / FAF8F4. Deterministic, replay-safe. |
| Visual trigger fix | `pptx_visual_assets.py` | Word-boundary marker matching ("ai" no longer matches "plain") + plain/internal veto list. |
| Stale smokes repaired | `office_theme_smoke.py`, `pptx_rejected_delivery_smoke.py` (fake signature + honest not-final delivery contract), `pptx_rescue_flow_smoke.py` (rendered-title markers) | All previously failing PPTX smokes now pass and pin current production behavior. |
| Smoke | `document_species_smoke.py` (new) | Real-prompt regression: distinct schemas, 9-day itinerary enforcement, distinct arc closings, saved-file accent/background assertions. |

## 5. Domain Knowledge Retrieval (deterministic RAG)

| Change | Files | What changed |
| --- | --- | --- |
| Retrieval engine | `domain_knowledge.py` (new) | Skill files in `maya_skills/active/` with a `## Knowledge Base` section become domain packs. Triggers parsed from the skill file itself (strong = quoted/parenthesized/acronyms, weak = 2+ matches, phrase vetoes). Lexical chunk scoring, retrieval-order boosts, 6k-char budget, min-overlap gate (silence over noise), whole-file retrieval for anything under `recipes/`, mtime caching. |
| Registry wiring | `skill_registry.py` | Domain block appended to skill context; activations logged as `domain:<skill_id>`. |
| Finance pack (mine) | `maya_skills/proposed/finance_credit_analysis.md`, `docs/finance/` (9 files) | 3 concept docs + 5 worked recipes (liquidity gap, R&R quality, ROA reliability, preference-share feasibility, survival playbook), formulas + worked examples matching your banking case class. Passes the skill scaffold validator. |
| Networking pack (authored by the other session) | `maya_skills/proposed/network_engineering.md`, `docs/networking/` | I verified format/scaffold compliance and wired retrieval to it; content authorship is not mine. |
| Smoke | `skill_domain_smoke.py` (new) | Parsing, activation/veto, whole-recipe retrieval with citations, budget, proposed-stays-inert, finance case routing. |

## 6. Skill Keyword Matching Fix (this round)

`skill_registry.py`: built-in skill keywords now match on word boundaries, and
the two genuine word-collision keywords were tuned (`book` → book a/book me/
booking; `share` → share this/the/it/with). Your banking case prompt now
injects **zero** spurious skills (was: Checkout Guard via "re**pay**ments",
Telegram Send via "Preference **Share**"). Hotel-booking and "share this to
telegram" phrasing still triggers correctly.

---

## New Environment Flags

| Flag | Default | Purpose |
| --- | --- | --- |
| `TELEGRAM_ALLOWED_CHAT_IDS` | *(set to your chat id in `.env`)* | Closed-by-default sender allowlist. Bot ignores everyone else. |
| `MAYA_AGENTIC_LOOP` | `0` | Set `1` to let harness runs plan/act/verify in a loop (needs `OPENAI_API_KEY`). |

## Verification Status (honest)

- Verified by deterministic smokes in my sandbox (Linux, Python 3.10, no live
  keys): everything above; ~40 smokes run repeatedly, all green at the end.
- **Not verifiable in my sandbox, needs your iMac**: live provider calls
  (`document_actions_smoke` cost lane, semantic artifact router), PPTX visual
  rendering with your fonts, `word_simple_edit_smoke` (sandbox time cap),
  live Telegram, live voice, the real GPT planner in the agentic loop, and
  everything from the concurrent session (browser extension lane, cost-lane
  refactor).
- Sandbox quirk you may ignore: I ran harness smokes with
  `MAYA_BROWSER_EXTENSION_WAIT_SECONDS=0` because the new (concurrent)
  browser extension bridge waits for a connection at `HarnessTools` init.
  On your iMac with the extension installed this should not block — but if
  smokes suddenly run slow, that wait is the first place to look.
