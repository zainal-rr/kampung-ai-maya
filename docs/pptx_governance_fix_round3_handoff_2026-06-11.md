# Handoff Round 3: PPTX Fragment Caps, Visual-Stage Budget, Review-Deck Honesty

Date: 2026-06-11
Author: Claude (Cowork session)
For: the live-testing session — validate, then re-run the three failed PPTX prompts.
Source: `phase-4-pptx-round2-live-rerun-2026-06-11-143900.md` (2/5 on `c3f2f09`)
plus live DB evidence pulled from `harness_artifacts` / `artifact_reviews`.
Builds on rounds 1–2 (closings/routing/image-policy: all CONFIRMED FIXED live —
robotics and agriculture now pass clean).

## The decisive evidence (from your own DB)

The polish reasons for the remaining draft-onlys, from `harness_artifacts`:

```
Design polish: draft-level. Slides 2 and 6 contain incomplete fragments
('All 5 Core User', 'Move Peer Reviews', 'Late Design Mocks Caused') ...

Design polish: draft-level. Multiple slides end in incomplete fragments:
'Inspecting Critical Infrastructure Is Still Done', 'Manual Methods Generate
Dark', 'Eliminate Weeks Of Manual' ...
```

**Claude polish is not "too strict" — it is correctly catching fragments that
Maya's own title shorteners manufacture.** `_title_words(text, 7)` chops
"…Is Still Done **Manually**" at the word cap; the stopword strip missed
participles ("Done", "Dark", "Manual"); `_short(…, 54)` does the same at the
layout layer. Polish flags the stumps → draft-level → draft-only. The
architecture deck's draft-level (review id 378, WITH 5 images inserted) is the
same fragment class.

---

## Fix A — Fragment-free title caps (`office_pptx_text.py`)

1. **Grace rule** in `_title_words(text, count)`: if the complete claim is
   ≤ `count + 3` words, keep ALL of it. A complete 10-word title beats a
   7-word fragment. (`_TITLE_CAP_GRACE = 3`.) All four live fragments had
   originals within grace range.
2. **Wider dangling-word set** (`_DANGLING_WORDS`, replaces the old `stop`
   set): adds participles/auxiliaries seen live — done, still, being, been,
   not, very, more, most, new, each, per, via, has/have/had, will/would,
   can/could/should/must, while/when/where/because/that/this.
3. **Layout-level cut hygiene** in `_short(...)`: after the final character
   cut, trailing `_DANGLING_WORDS` are stripped so a clipped title ends on a
   content word ("…Is Still Done" → "…Infrastructure") instead of mid-claim.

Validation: `_fragment_cap_checks` in the governance smoke uses the EXACT
live fragments as fixtures. All deck-related smokes re-run green (the grace
rule changes rendered titles, so `powerpoint_golden_artifact_smoke`,
`pptx_rescue_flow_smoke`, `everyday_commands_smoke` were the regression
risks — all pass).

## Fix B — Visual stage: wall-clock budget + local scratch (drone 313.9s)

1. `pptx_document_flow.py`: the whole `add_gemini_visual_asset` stage now
   runs under `asyncio.wait_for` with `MAYA_PPTX_VISUAL_BUDGET_SECONDS`
   (default 120, `0` disables). On timeout → the round-2 availability-note
   path ("visual stage exceeded its Ns budget"), deck delivers.
2. `pptx_visual_assets.py`: generated-image scratch moves OFF Desktop —
   `_image_scratch_dir()` defaults to `<tmp>/maya-pptx-images`, override
   `MAYA_PPTX_IMAGE_SCRATCH_DIR`. The pngs are intermediate (they embed into
   the .pptx); writing them to the iCloud-synced
   `Desktop/Maya/artifacts/pptx-images` is what produced the Errno 60 stall
   in your round-2 P3 reply text. No behavior change other than location.

Expected live change: drone deck bounded at roughly visual-budget + drafting
time per attempt; images either embed (healthy path, now on local scratch) or
the deck ships with the availability note. The remaining "slide 4 incomplete
sentence" blocker from round 2 is addressed by Fix A (it was the same
fragment class, flagged by local QA's truncation check).

## Fix C — Review/pitch deck honesty contract (sprint deck "semantically wrong")

The sprint deck fabricated specifics ("Sprint 24", invented metrics) because
the drafter had no data and no instruction not to invent it.

1. `deck_species.py`: new `deck_species_prompt_context(species)` —
   - `review`: do NOT invent sprint numbers/velocity/ticket/team names; use
     marked fill-in slots ("Sprint <N>", "<X> story points"); say in speaker
     notes which slots the user must fill.
   - `pitch`: do NOT fabricate traction/revenue/customers/market sizes;
     fill-in slots for anything not provided.
   - all other species: empty string (no behavior change).
2. `document_actions_office.py` `_create_powerpoint`: contract injected via
   the existing `_draft_markdown(..., extra_context=...)` mechanism (same as
   the Excel species contract; smoke fakes unaffected).

Expected live change: a data-less "sprint review deck" comes back as an
honest fill-in structure instead of a fictional Sprint 24. Judgment call for
your eyes: if you'd rather Maya ASK for the sprint data before building,
that's a different (interactive) design — say so and it becomes a follow-up.

## Files changed

| File | Change |
| --- | --- |
| `office_pptx_text.py` | `_DANGLING_WORDS` set, `_TITLE_CAP_GRACE` rule in `_title_words`, dangling strip in `_short` final cut |
| `pptx_document_flow.py` | visual stage `asyncio.wait_for` budget + `_visual_budget_seconds()` |
| `pptx_visual_assets.py` | `_image_scratch_dir()` (tmp default, env override), scratch path swap |
| `deck_species.py` | `deck_species_prompt_context()` honesty contracts |
| `document_actions_office.py` | contract injection in `_create_powerpoint` + imports |
| `pptx_closing_governance_smoke.py` | +3 checks (10 total): live-fragment fixtures, visual budget note, scratch dir + contracts |

New env: `MAYA_PPTX_VISUAL_BUDGET_SECONDS` (default 120),
`MAYA_PPTX_IMAGE_SCRATCH_DIR` (default system tmp).

## Validation

Sandbox: governance smoke 10/10 checks; regressions all green:
`pptx_quality_gate_smoke`, `pptx_rescue_flow_smoke`, `pptx_rejected_delivery_smoke`,
`pptx_visual_assets_smoke`, `powerpoint_golden_artifact_smoke`,
`presentation_design_review_smoke`, `pptx_polish_review_smoke`,
`document_species_smoke`, `office_theme_smoke`, `everyday_commands_smoke`.

Live re-test order:

1. `make a presentation about Kampung AI architecture` → expect clean pass:
   the draft-level cause (fragments) is fixed at the source. If polish still
   says draft-level, read the polish reason in `harness_artifacts` — if it
   names something OTHER than fragments, that's a genuine quality verdict.
2. `make an investor pitch deck for a drone inspection startup` → expect
   bounded time (~2-3 min worst case), images embedded from local scratch or
   honest availability note; no fragment blocker.
3. `make a sprint review deck for the team` → expect fill-in slots
   ("Sprint <N>") instead of fabricated "Sprint 24"; judge whether the
   honesty contract output is what you want.
4. Then Phase 5, per the validation checklist.

## Open items (your lanes)

1. iCloud Desktop: scratch + review renders now avoid it, but every OTHER
   Maya artifact (docx/xlsx/pptx finals) still lands on `Desktop/Maya`. If
   stalls appear elsewhere, the durable fix is moving `MAYA_WORKSPACE_ROOT`
   off the synced volume or excluding the folder from sync.
2. `KAMPUNG_AI_UI/` untracked — yours, untouched.
3. If you want "ask before building data-dependent decks" instead of
   fill-in slots, say so — that's an interactive flow change, not a patch.
