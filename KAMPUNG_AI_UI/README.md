# Kampung AI UI

Everything for the Maya text UI lives in this folder. Nothing else in the repo touches it.

| File | What it is |
| --- | --- |
| `maya_ui_requirements.md` | Complete UI requirements derived from reading ALL architecture docs (KAMPUNG_AI.md, FULL, CHECKLIST Phases 1-25, doctrine, proof, public architecture) |
| `maya_text_ui_design_plan.md` | The original design plan (visual direction, layout, motion, stack, build phases) |
| `taste_skill_reference.md` | Saved copy of the Taste Skill design rules (github.com/Leonxlnx/taste-skill) — the design system we follow |
| `mockups/design_b2_bento_expanded.html` | **CHOSEN DIRECTION** — expanded Bento design: light + dark theme toggle, 5 views (Desk / Conversation / Memory / Artifacts / Proof), Living Bamboo brand, no engine names (lanes shown as The Sight / The Mind / The Steward / The Pulse / The Artisan). Conversation view is a Codex-style workspace: Desktop/Maya directory tree (left) · chat mixing normal chat and work runs (center) · selected-file + run-trace context (right) |
| `mockups/design_b_bento.html` | Design B v1 — original light bento mockup (kept for reference) |
| `mockups/design_a_cockpit.html` | Design A — dark mission-control cockpit (not chosen) |
| `mockups/design_c_holo.html` | Design C — 3D holo terminal with animated background (not chosen) |

## Decisions so far (2026-06-11)

1. Direction: Design B (bento), expanded as `design_b2_bento_expanded.html`.
2. No model/provider names anywhere in the UI — masked team names only.
3. Light and dark themes both supported via the toggle (persisted).
4. Brand: Living Bamboo — bamboo green + warm gold signal nodes, no purple/neon/robot motifs (approved PNG used as the mark, pastel palette sampled from it).
5. LLM Council review (`maya_ui_council_review.md`) accepted and implemented: Automations tab (routines unified, last-outcome always visible), alert bell with two tiers, Stop-all button, Live runs panel with blast radius + steering, gate-decision transparency, artifact diff surface, isolated-worktree badge.

## How to view mockups

Open any `mockups/*.html` file in a browser. They are self-contained; fonts load from CDN (internet needed on first view).

## Next steps

Phase 1: approve the expanded B2 visual. Phase 2: read-only client over the event store. Phase 3: composer + approvals round-trip. See `maya_text_ui_design_plan.md` section 8.


## Phase 2 — read-only live server (2026-06-11, draft until Zainal locks it)

| Path | What it is |
| --- | --- |
| `SSE_PROTOCOL.md` | One-page wire contract (cursor, reconnect, error envelope, masking rule) |
| `server/` | FastAPI read API — `readers_common.py` (ro connection + lane masking), `event_reader.py` (cursor tail), `state_reader.py` (desk snapshot), `app.py` (routes + token gate). All 59–107 logical lines, well under the 300 rule |
| `static/` | Live client — index.html / style.css / app.js + logo. Light default, dark toggle |

Run it:
```bash
cd KAMPUNG_AI_UI
pip install -r server/requirements.txt
MAYA_UI_TOKEN=yourtoken python -m uvicorn server.app:app --port 8765
# open http://127.0.0.1:8765/?token=yourtoken
```

Guarantees: SQLite opened with `?mode=ro` (cannot write), zero POST/PUT/DELETE routes, no kampung-ai module imports, no kampung-ai file modified. Engine names are masked server-side (prose + snake_case keys); desk payload verified leak-free against live data.

Pending items that DO require touching kampung-ai (left for Maya/Artisan approval flow): `schema_version` column on event tables; one doc sentence in KAMPUNG_AI.md clarifying the logical-line counting; `canonical_memory.py` split.
