# Handoff: Telegram Intake Guard + Excel Species Drafting Contract

Date: 2026-06-11
Author: Claude (Cowork session)
For: the session owning live testing / validator work — review, validate, then re-run the blocked Phase 4/5 items.
Source findings: `kampung-ai-phase-4-5-live-test-report-2026-06-11.md` (Findings 1, 2, 3).

This document is written so every change can be independently verified without
trusting this session. Each section states: root cause → exact change →
how to validate → what was deliberately NOT touched.

---

## Part A — Telegram Intake Guard (live report Finding 1)

### A1. Root causes (two, compounding)

1. **Duplicate poller.** `logs/launchd.stderr.log` showed
   `telegram.error.Conflict: terminated by other getUpdates request`.
   Two processes existed (app controller pid 9355, engine pid 70022). Two
   getUpdates loops on one token make Telegram kill connections; whichever
   instance wins the race consumes the update.
2. **Invisible mid-turn death.** The trace signature was: `skill_usage_events`
   rows written (19:30:05, 19:38:03 UTC) but NO `telegram_turn_events` row.
   Mechanism: skill usage is recorded early inside `assistant.handle_text`
   (during `build_prompt_context`); the turn row was only written at the END
   of `TelegramChannel._handle_text`. When the conflicting poller killed the
   connection, the in-flight task was **cancelled** — and
   `asyncio.CancelledError` is a `BaseException`, so the old
   `except Exception` never fired and the "failed" row was never written.
   Result: a visible user message with zero backend trace.

### A2. Changes

**`telegram_turn_log.py`** — three new functions, existing functions untouched:

- `record_telegram_turn_received(db_path, *, chat_id, input_type, prompt) -> int`
  — inserts a row with `status='received'`, returns the row id.
- `finalize_telegram_turn(db_path, turn_id, *, status, duration_ms, response_chars, response_preview, error)`
  — UPDATEs that same row to `completed`/`failed`. One row per turn, same
  end-state schema as before (analytics counting completed/failed see no change).
- `count_orphaned_received_turns(db_path)` — rows stuck at `received` = the
  disappearance signal, now queryable.

**`telegram_channel.py`** — `_handle_text` lifecycle rewritten:

1. Row inserted with `status='received'` BEFORE `assistant.handle_text` runs.
2. On success: `_finalize_turn(... 'completed' ...)`.
3. `except BaseException` (deliberate — catches CancelledError): finalize
   `'failed'` with the exception class name, then re-raise.
4. The finalize write is wrapped in `asyncio.shield(...)` so it completes even
   while the surrounding task is being cancelled.
5. Fallback: if the received-insert itself failed (turn_id None), finalize
   falls back to the old insert path (`record_turn_event`) so audit is never
   lost. Photo and direct-command paths are unchanged (they keep `_record_turn`).

**`telegram_channel.py` `run()`** + new **`telegram_poller_lock.py`**:

- `acquire_poller_lock("telegram")` — fcntl flock on `logs/telegram_poller.lock`
  (gitignored dir), pid written into the file. Held for process lifetime; OS
  releases it automatically if the process dies (no stale-lock wedge).
- If the lock is held elsewhere: CRITICAL log naming the holder pid, sleep
  `MAYA_TELEGRAM_POLLER_RETRY_SECONDS` (default 30) so the supervisor doesn't
  hot-loop, then return. The polling body moved unchanged into `_run_polling()`.
- `MAYA_TELEGRAM_POLLER_LOCK=0` disables (deterministic tests only).

### A3. Validate

```
python3 telegram_intake_guard_smoke.py        # deterministic, no live deps
```
Covers: received-row-exists-mid-handling, finalize-to-completed (exactly one
row), crash → failed row, **CancelledError → failed row** (the live vanish
case), lock acquire/refuse/release cycle.

Live validation (the report's "tomorrow plan" step 1-2):
1. Confirm only one process polls: `lsof logs/telegram_poller.lock` shows one pid.
2. Start a second engine manually → it must log CRITICAL and not poll.
3. Send the sprint deck prompt again. If anything dies mid-turn now, you get a
   `telegram_turn_events` row with status `received` or `failed` — run
   `SELECT * FROM telegram_turn_events WHERE status='received'` to find orphans.
4. The launchd setup still needs YOUR review: why did the app controller and
   engine both reach poller startup? The lock makes it safe; the double-start
   itself is config debt I did not touch.

### A4. Not touched (your lanes)

- The launchd plist / app-controller startup duplication itself.
- Voice/photo/command handler turn semantics (insert-at-end, as before).
- Anything in the browser extension bridge.

---

## Part B — Excel Species Drafting Contract (live report Findings 2 + 3)

### B1. Root cause

`markdown_drafter._prompt` rule 4 literally instructed Gemini, for
spreadsheets, to "**describe** useful columns, rows, formulas, statuses" —
so Gemini wrote proposal documents, and `office_drafter.spreadsheet_from_markdown`'s
species path mapped narrative section lines into cells. Hence: correct species
columns (the part that worked), prose rows, phantom "three-sheet systems",
formulas as text (the part that failed all six Claude reviews).

### B2. Changes

**New `excel_species_draft.py`** — the contract, parser, and seeds:

- `excel_species_prompt_context(species, topic)`: appended to the Gemini
  prompt for species topics. Demands ONE markdown table with EXACTLY the
  species header (pinned verbatim from `excel_species._SCHEMAS`), 8–14 data
  rows, per-species row guidance, bans prose rows / sheet-dashboard claims /
  text formulas. Explicitly overrides the document-section standard.
- `rows_from_species_draft(species, markdown) -> rows | None`: extracts the
  first markdown table; header must match the schema (>=70% normalized column
  match, same count); strips bold/backticks; drops `=`-prefixed text formulas;
  drops rows containing `NARRATIVE_ROW_MARKERS` ("executive summary",
  "three-sheet", "dashboard", "sheet 2", ...); financial rows get bucket
  normalization to `FINANCIAL_BUCKETS` and forced-empty Net/Cumulative
  (formulas own those). Returns **None** if <5 valid rows or more narrative
  than data — None means "draft untrusted".
- `seed_rows(species)`: deterministic practical fallback rows
  (content calendar: 6 real post plans; farm ops: 6 operations; dev tracker:
  6 tickets; financial model: 8 line items across **varied** time buckets —
  fixing the live "every row 0-3 months" defect). Rationale: the monthly
  budget builder passed live precisely because its content is deterministic.

**`excel_species.py`** — new `species_rows_structured(species, topic, rows)`:
assembles a workbook from explicit rows; `_FILL_PLAN` defaults fill only
EMPTY cells (drafted buckets/statuses are never overwritten); formula passes
(`_with_financial_formulas`, `_with_inventory_formulas`) always rebuild
computed columns. Old `species_rows` (sections-based) kept for compatibility
but no longer used by the drafter path.

**`office_drafter.py`** `spreadsheet_from_markdown` species branch:
`rows_from_species_draft(...) or seed_rows(...)` → `species_rows_structured(...)`.
Prose section-mapping for species topics is gone. Non-species lanes
(comparison, budget, generic) byte-identical.

**`document_actions.py`** `_draft_markdown(..., extra_context="")`: optional
param appends the contract to the preflight context block. Chosen over
changing `draft_markdown_with_gemini`'s signature so every existing smoke
fake (`fake_draft(db_path, topic, preflight_context="")`) keeps working —
verified by running those smokes.

**`document_actions_office.py`** `_create_excel` generic path + `rebuild_generic`
repair pass: compute `species_contract` once, pass as `extra_context` to both
the initial draft and every repair draft (so repairs also return tables, not
prose). Imports added: `detect_excel_species`, `excel_species_prompt_context`.

### B3. Validate

```
python3 excel_species_draft_smoke.py          # deterministic
```
Covers: contract pins exact headers + bans prose; the live prose-draft
failure mode parses to None; good table drafts survive with values intact;
text formulas stripped; drafted financial buckets kept and varied; gap +
coverage-ratio formula rows rebuilt; seeds are narrative-free with varied
buckets; end-to-end `spreadsheet_from_markdown` never lets "executive
summary"/"dashboard"/"three-sheet" into cells; comparison lane regression.

Regressions run and green alongside it: `document_species_smoke`,
`excel_golden_artifact_smoke`, `route_no_overwrite_smoke`,
`telegram_commands_smoke`, `telegram_voice_reply_policy_smoke`.

Live validation: re-run the three trackers + liquidity prompts from Phase 4.
Expected delivery change: clean "Done." instead of "could not get through QA
after 3 attempts", rows containing data (drafted or seeded), no phantom-sheet
claims. If Gemini still returns prose, the file now contains seed data —
usable, honest, and visibly generic enough that you'll know the draft failed
(check `rows_from_species_draft` returning None in a debug run).

### B4. Not touched (your lanes)

- `validate_xlsx_path` / Excel QA rules — a species-aware closed-world rule
  ("species rows must not contain narrative markers") would be a good
  **blocker-tier validator** under the severity-tier design; left to the
  validator owner to avoid collision.
- Word empty-section/truncation repair (report Finding 4).
- PPTX closing leak + image-policy contradiction (Finding 5) — note for that
  work: the leaked titles come from `pptx_slide_repair.rescue_slides`
  templates plus the `office_pptx_text` visual-title rewrite of
  "Recommendation:" headings; fix both, and put the no-generic-closing smoke
  at `create_powerpoint_with_qa` level, not the drafter level.
- `/review` chronological grouping (Finding 6).

---

## Files changed in this slice

| File | Change |
| --- | --- |
| `telegram_turn_log.py` | +`record_telegram_turn_received`, +`finalize_telegram_turn`, +`count_orphaned_received_turns` |
| `telegram_channel.py` | turn-first lifecycle in `_handle_text` (+`_finalize_turn`, BaseException + shield), poller lock in `run()` (+`_run_polling`) |
| `telegram_poller_lock.py` | NEW — flock single-poller lock |
| `excel_species_draft.py` | NEW — contract, parser/validator, seeds |
| `excel_species.py` | +`species_rows_structured` (assembly from explicit rows) |
| `office_drafter.py` | species branch → structured rows, prose mapping removed |
| `document_actions.py` | `_draft_markdown` +`extra_context` param |
| `document_actions_office.py` | contract passed to initial + repair excel drafts; 2 imports |
| `telegram_intake_guard_smoke.py` | NEW smoke |
| `excel_species_draft_smoke.py` | NEW smoke |

New env flags: `MAYA_TELEGRAM_POLLER_LOCK` (default 1), `MAYA_TELEGRAM_POLLER_RETRY_SECONDS` (default 30).
DB change: none structural — `telegram_turn_events` gains the transient `received` status value; end states unchanged.

## Suggested re-test order (unchanged from the live report)

1. `python3 telegram_intake_guard_smoke.py && python3 excel_species_draft_smoke.py` on the iMac.
2. Restart service; confirm single poller (lock file pid).
3. Re-send sprint deck prompt → intake stable.
4. Re-run tracker + liquidity prompts → usable workbooks.
5. Then your lanes: Word repair, PPTX closing/image policy, Phase 5 promotion.
