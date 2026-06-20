# Handoff Round 2: PPTX Live-Path Fixes (Storage Stalls, Image Policy, Availability Notes)

Date: 2026-06-11
Author: Claude (Cowork session)
For: the live-testing session — validate, then re-run the four failed PPTX prompts.
Source: `phase-4-pptx-live-rerun-2026-06-11-135452.md` (1/5 pass on commit `1c67dde`).
Builds on: `docs/pptx_governance_fix_handoff_2026-06-11.md` (round 1 — routing and
closings, both CONFIRMED FIXED live in the rerun).

## The unifying diagnosis

Round 1's render timeout guarded the wrong layer. The rerun's P5 error is the
key evidence: `render failed: [Errno 60] Operation timed out:
'.../Desktop/Maya/screenshots/pptx-reviews/...-slide-01.jpg'`.

**Errno 60 (ETIMEDOUT) from `image.save()` is an OS-level stall inside a
single file-write syscall.** Round 1's deadline only checked BETWEEN slides,
so a write stuck for 7 minutes inside slide 1 never hit it. Errno 60 on local
APFS is essentially impossible — on an iCloud-synced Desktop it is typical.
One stalled-writes hypothesis explains every failure in the rerun:

- P5 (434s): review render stalls writing jpgs to `Desktop/Maya/screenshots/` → blocker → draft-only.
- P3 (307s): image generation/fallback stalls writing pngs to `Desktop/Maya/artifacts/` → `visual_added=False` → "visual topic needs image" blocker → draft-only.
- P2/P4 (~40s): no stall, but Claude polish graded "missing visuals for a
  visual topic" as draft-level for decks the CODE decided need no images —
  the image-policy contradiction flagged as an open item in the first live
  report, now fixed.

**ACTION FOR YOU (environmental, not code): check whether `Desktop/Maya` is
on an iCloud-synced volume** (System Settings → Apple ID → iCloud → Drive →
Desktop & Documents). If yes: either exclude/disable sync for it, move
`MAYA_WORKSPACE_ROOT`, or at minimum set `MAYA_PPTX_REVIEW_DIR=/tmp/maya-pptx-reviews`
(new env, below). The code fixes below make Maya RESILIENT to the stalls;
they do not make the disk faster.

---

## Fix 1 — Wall-clock render budget at the gate (P5)

`pptx_quality_gate.py`:

- New `_render_with_wall_clock_budget()`: runs `render_pptx_slides` in a
  worker thread, `future.result(timeout=budget+15)` where budget =
  `MAYA_PPTX_RENDER_TIMEOUT_SECONDS` (default 90, `0` disables). A render
  stuck INSIDE one syscall now gets abandoned (thread orphaned via
  `shutdown(wait=False)` — it holds no locks; worst case one orphan jpg
  finishes writing later). Raises `PptxRenderTimeout` → warning note.
- `OSError` with `errno` 60/110 (ETIMEDOUT) from the render is classified as
  the SAME warning class, with a note that names the likely cause and the
  `MAYA_PPTX_REVIEW_DIR` escape hatch. All OTHER render errors remain
  blockers (corrupt file must still fail) — smoke-pinned both directions.
- `_review_dir()` honors new env `MAYA_PPTX_REVIEW_DIR` (point review renders
  at a guaranteed-local path).

Expected live delivery change for P5: "Done. ... Visual QA passed. Note:
render QA skipped (...)" in ≤ ~105s worst case, instead of 434s → draft-only.

## Fix 2 — Visual-asset availability is a note, never a blocker (P3)

`pptx_document_flow.py` (`_run_powerpoint_attempt`):

- `visual_added=False` on a visual topic → `qa.notes` gets
  "visual assets unavailable (<reason>); delivered without images" and the
  deck DELIVERS. Previously: hard `qa.passed=False`.
- Images inserted but fewer than suggested → note
  ("got N of M suggested images"), not a blocker.
- Rationale (severity tiers): image availability reflects provider/storage
  health, not deck quality. The reviewer still judges overall design.

## Fix 3 — Image policy single source of truth (P2/P4)

`pptx_polish_review.py`:

- New `image_policy_line(topic)`: derives the image expectation from the same
  `topic_benefits_from_visuals()` the generation pipeline uses. Non-visual
  topic class → "this topic class does not use generated images; do not
  mention missing images at all." Visual class → "missing images are a
  non-blocking improvement note, never a blocker or draft-level reason."
- `_user_prompt(path, topic)` embeds that line and the hardcoded
  "missing visuals for a visual topic" draft-level criterion is REMOVED from
  the prompt. `claude_polish_grade(db_path, path, topic="")` gains the topic.
- `pptx_document_flow` calls it through `_polish_grade_with_topic()` which
  introspects the signature first — so every existing smoke fake patched as
  `(db_path, path)` keeps working unmodified (same pattern as `_draft_markdown`).

Expected live change for P2/P4: robotics and agriculture decks stop being
graded draft-level for missing images. NOTE: if Claude still grades them
draft-level for a REAL design reason, they will still draft-only — that
would then be a genuine quality verdict, visible in the polish text.

## Files changed

| File | Change |
| --- | --- |
| `pptx_quality_gate.py` | wall-clock budget thread, Errno 60/110 → warning, `MAYA_PPTX_REVIEW_DIR` override |
| `pptx_document_flow.py` | `_qa_note` helper; availability → notes; `_polish_grade_with_topic` (signature-safe topic pass) ; body moved to `_run_powerpoint_attempt_impl` (wrapper keeps the public name/signature) |
| `pptx_polish_review.py` | `image_policy_line()`, topic param, prompt criterion removed |
| `pptx_closing_governance_smoke.py` | +3 checks: Errno-60 stall = warning / real failure = blocker; flow-level availability note; policy line both classes |

New env: `MAYA_PPTX_REVIEW_DIR` (optional). Existing: `MAYA_PPTX_RENDER_TIMEOUT_SECONDS` now enforced as true wall-clock.

## Validation

Sandbox (deterministic, all green): `pptx_closing_governance_smoke` (7 checks),
`pptx_quality_gate_smoke`, `pptx_rescue_flow_smoke`, `pptx_rejected_delivery_smoke`,
`pptx_visual_assets_smoke`, `powerpoint_golden_artifact_smoke`,
`presentation_design_review_smoke`, `pptx_polish_review_smoke`, `document_species_smoke`.

Live re-test order:

1. FIRST: check the iCloud/Desktop sync question above; optionally set
   `MAYA_PPTX_REVIEW_DIR=/tmp/maya-pptx-reviews` in `.env`. Restart.
2. `make a presentation about Kampung AI architecture` → expect clean or
   passed-with-note delivery in ≤ ~2 min, never a 7-minute hold.
3. `make a presentation about a school robotics workshop` and the agriculture
   deck → expect clean delivery (no draft-level-for-images), distinct closings.
4. `make an investor pitch deck for a drone inspection startup` → expect
   delivery WITH images if generation is healthy, or delivery with the
   "visual assets unavailable" note if it is not — never draft-only for
   image availability. If this prompt still takes 300s, the time is in the
   Gemini image lane + stalled artifact writes: same iCloud question, plus
   `PPTX_GEMINI_IMAGE_TIMEOUT` tuning is available.
5. Then Phase 5 promotion, per the validation checklist.

## Open items (unchanged, your lanes)

1. The iCloud/Desktop investigation itself (root environmental cause).
2. Renderer perf profiling if stalls persist on a local disk.
3. `docs/design/` untracked dir — your call to commit or remove (not mine,
   per your note it is out of this fix's scope).
