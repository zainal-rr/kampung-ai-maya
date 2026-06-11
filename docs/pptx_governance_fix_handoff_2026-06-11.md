# Handoff: PPTX Governance Fixes (Closing Leak, Review Routing, Render Timeout)

Date: 2026-06-11
Author: Claude (Cowork session)
For: the session owning live testing — validate, then re-run the four blocked Phase 4 PPTX items.
Source findings: `phase-4-documents-live-test-2026-06-11-120635.md` (PPTX section: robotics/drone/agriculture closing leak, sprint-review misroute, 453s render hold).
Scope discipline: **zero Word or Excel changes** — those passed live and are frozen, per instruction.

Each section: root cause → exact change → how to validate → what was NOT touched.

---

## Fix 1 — The closing-slide leak ("Make The Recommendation Clear")

### Root cause (two layers, one funnel)

1. **The funnel**: `office_pptx_text.py` `_visual_title()` had a mapping —
   `(("proposal", "recommendation"), "Make The Recommendation Clear")` — that
   rewrote ANY slide title containing either word into the one banned generic.
   `create_pptx` passes every heading from every path through `_visual_title`,
   so the species arcs' distinct closings survived the drafter only to be
   mangled at render time whenever a title or a Gemini "Recommendations"
   heading hit the mapping. This is why the earlier drafter-level smoke passed
   while live decks leaked.
2. **The feeder**: all three leaked live decks (robotics, drone, agriculture)
   had gone through the QA **rescue path**, and 9 of the `rescue_slides`
   templates in `pptx_slide_repair.py` ended with `"Recommendation: ..."`
   titles — guaranteed hits on the mapping.

### Changes

- `office_pptx_text.py`: the mapping entry is **removed** (comment left in
  place explaining why, dated). Species arcs and rescue templates now own
  their closings. All other mappings untouched.
- `pptx_slide_repair.py`: the literal prefix `"Recommendation: "` stripped
  from all 9 rescue closings (`"Recommendation: Make It Practical"` →
  `"Make It Practical"`, etc.). **Why this is required and not cosmetic**:
  with the mapping gone, `_visual_title`'s fallthrough splits a title at the
  first colon (`re.split(r"[:.]", text, 1)[0]`), so every rescue closing
  would have rendered as the bare word "Recommendation" — same sameness,
  new spelling. Stripping the prefix lets each distinct closing survive:
  Watch Then Apply / Start Narrow / Build Skills, Not Prompts / Plan For
  Flexibility / Prioritize Resilience / Start With Guardrails / Decide In
  Stages / Prototype The Feel / Make It Practical.

### Validate

- `python3 pptx_closing_governance_smoke.py` — asserts on **saved .pptx
  titles** (after every transformation layer): four species decks have four
  different closings, no slide anywhere titled the banned generic; the
  rescue-template path keeps a real closing and does not collapse to bare
  "Recommendation".
- Live: re-run robotics, drone (pitch), agriculture (issue) deck prompts;
  open the files; final slide titles must differ and never be the generic.

---

## Fix 2 — Sprint review deck misroute (review instead of create)

### Root cause

`presentation_design_review.wants_presentation_review()` matched on bare
substrings: `("review"|"critique"|"check") AND ("deck"|"presentation"|...)`.
"make a **sprint review deck**" satisfied both → Maya reviewed the previous
deck instead of creating one. Same class of bug as "pay" ⊂ "repayments"
(sixth occurrence this week). Review-as-subject deck types (sprint review,
performance review, quarterly review, code review) are creation requests.

### Change

`wants_presentation_review` now applies a creation guard: if the text
contains a creation verb (make/create/build/draft/generate/prepare), it is
NOT a review request — unless it explicitly says "review|critique|check
the/this/that/it/my/our/last/latest/previous" (regex `_EXPLICIT_REVIEW_RE`).
The existing pinned case ("review the Meta Ray-Ban Display presentation
design") still routes to review — verified by the untouched
`presentation_design_review_smoke`.

### Validate

- Smoke covers: 4 creation phrasings (sprint review deck, performance review
  deck, quarterly review presentation, code-review-process deck) → all route
  to creation; 4 review phrasings → all still route to review.
- Live: send `make a sprint review deck for the team` → a NEW deck file must
  appear under `Desktop/Maya/presentations` (this was the blocked live item).

---

## Fix 3 — Render QA timeout held a correct deck for 453s

### Root cause

`pptx_quality_gate.inspect_pptx_quality` calls `render_pptx_slides(...)`
(pure-PIL renderer) with **no time bound**. A pathological slow render held
the turn 453s, and any render problem was appended to `issues` — i.e. treated
as a blocker — so a structurally correct deck was delivered "not final".

### Changes

- `pptx_slide_renderer.py`: `render_pptx_slides` gains a deadline — checked
  before each slide — raising new `PptxRenderTimeout(TimeoutError)`. Budget:
  `MAYA_PPTX_RENDER_TIMEOUT_SECONDS`, default 90, `0` disables. Signature is
  backward compatible (`deadline_seconds: float | None = None` appended).
- `pptx_quality_gate.py`: severity-tier behavior —
  - `PptxRenderTimeout` → **warning, not blocker**: recorded in a new
    `notes` field on `PptxQualityResult`, deck judged on structure only,
    slide-count-vs-render check skipped (it would always false-fail on
    timeout).
  - Any OTHER render exception remains a blocker (a corrupt file must fail).
  - `PptxQualityResult.notes: list[str] | None = None` appended as the LAST
    dataclass field — every existing positional construction stays valid.
  - `summary()` includes `Note: ...` so the Telegram delivery wording shows
    "Visual QA passed. Note: render QA skipped (...)" instead of draft-only.

### Validate

- Smoke forces the timeout deterministically (microscopic deadline via
  monkeypatch) on a clean deck → `passed=True`, note recorded, summary reads
  as passed; then runs the NORMAL render path on the same deck → still
  passes, no notes, rendered image count == slide count.
- Live: re-run the Kampung AI architecture deck. Expected: clean delivery in
  normal time; if the renderer ever stalls again, delivery says
  "Visual QA passed. Note: render QA skipped (...)" after ≤90s instead of a
  453s hold ending in "not final". The underlying renderer slowness on that
  deck is NOT diagnosed here (see open items).

---

## Files changed

| File | Change |
| --- | --- |
| `office_pptx_text.py` | removed the proposal/recommendation → generic-closing mapping (comment documents why) |
| `pptx_slide_repair.py` | 9 rescue closings: `"Recommendation: X"` → `"X"` (mechanical string replace, nothing else touched) |
| `presentation_design_review.py` | `wants_presentation_review` creation guard + `_CREATION_VERBS`/`_EXPLICIT_REVIEW_RE` |
| `pptx_slide_renderer.py` | deadline + `PptxRenderTimeout`; env `MAYA_PPTX_RENDER_TIMEOUT_SECONDS` (default 90) |
| `pptx_quality_gate.py` | timeout = note not blocker; `PptxQualityResult.notes`; summary shows notes |
| `pptx_closing_governance_smoke.py` | NEW flow-level smoke (saved-file closings, rescue path, routing, timeout-as-warning) |

## Regression evidence (sandbox, deterministic)

All green after the changes: `pptx_closing_governance_smoke`,
`pptx_quality_gate_smoke`, `pptx_rescue_flow_smoke` (its pinned rescue marker
"Follow The Neighborhood Spine" is a non-closing title — unaffected),
`pptx_rejected_delivery_smoke`, `pptx_visual_assets_smoke`,
`powerpoint_golden_artifact_smoke`, `presentation_design_review_smoke`
(pinned review case intact), `document_species_smoke`, `office_theme_smoke`.

## Deliberately NOT touched (open items, your lanes)

1. **Why the renderer took 453s** — the timeout contains the damage; the perf
   root cause (likely font loading or text-wrap pathology in `_draw_text` on
   that deck's content) is undiagnosed. Suggest profiling `render_pptx_slides`
   on `kampungai-architecture` deck content when convenient.
2. **The "non-blocking ... blocker" delivery wording contradiction** and the
   image-policy disagreement (`topic_benefits_from_visuals` vs Claude review
   demanding images for "visual topics") — from the previous report's
   Finding 5; unchanged in this slice.
3. Word/Excel: untouched by instruction.
4. Phase 5 skill promotion: still pending Telegram-stable confirmation.

## Suggested live re-test order

1. `python3 pptx_closing_governance_smoke.py` on the iMac.
2. Restart service. Send: sprint review deck → NEW file created (Fix 2 live proof).
3. Send: robotics workshop deck, drone investor pitch deck, agriculture concern deck → open all three, closings differ, no banned title (Fix 1 live proof).
4. Send: Kampung AI architecture deck → clean delivery, navy style, no 7-minute hold (Fix 3 live proof).
5. Then Phase 5 promotion + prompts, per the validation checklist.
