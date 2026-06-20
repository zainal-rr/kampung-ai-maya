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
5. LLM Council review (`maya_ui_council_review.md`) accepted as the target. Phase 2.5 now implements the read-only parts: Automations evidence, Proof evidence, alert bell, live runs, route/cost, memory audit, artifact sessions, and QA review visibility. Write controls such as Stop-all, artifact diff comments, approval buttons, and run steering wait for the Phase 3 MayaAppServer/permission-kernel protocol.

## How to view mockups

Open any `mockups/*.html` file in a browser. They are self-contained; fonts load from CDN (internet needed on first view).

## Next steps

Phase 1: approve the expanded B2 visual. Phase 2: read-only client over the event store. Phase 3: composer + approvals round-trip. See `maya_text_ui_design_plan.md` section 8.


## Phase 2.5 — read-only live server and proof cockpit (2026-06-14)

| Path | What it is |
| --- | --- |
| `SSE_PROTOCOL.md` | One-page wire contract (cursor, reconnect, error envelope, masking rule) |
| `server/` | FastAPI read API — read-only connection, lane masking, cursor tail, desk snapshot, proof logs, automations, memory audit, artifact QA/session projections, and token gate |
| `static/` | Live client — index.html / style.css / app.js / ui_extra.js + logo. Light default, dark toggle |
| `ui_read_api_smoke.py` | No-network API smoke using FastAPI TestClient |
| `schema_setup.py` | Explicit maintenance helper for adding `schema_version` to event tables. The live UI server never mutates the store |
| `start_ui.sh` | One-command local starter using the repo venv |
| `launchd/com.kampung-ai.maya-ui.plist.example` | Optional launchd template; not installed automatically |

Run it:
```bash
cd /Users/zainalabidinjamal/projects/kampung-ai
KAMPUNG_AI_UI/start_ui.sh
# open http://127.0.0.1:8765/?token=yourtoken
```

Alternative:
```bash
cd /Users/zainalabidinjamal/projects/kampung-ai/KAMPUNG_AI_UI
MAYA_UI_TOKEN=yourtoken ../venv/bin/python -m uvicorn server.app:app --port 8765
```

Smoke it:
```bash
cd /Users/zainalabidinjamal/projects/kampung-ai/KAMPUNG_AI_UI
../venv/bin/python ui_read_api_smoke.py
```

Guarantees: SQLite opened with `?mode=ro` (cannot write), zero POST/PUT/DELETE routes, no kampung-ai runtime imports inside the server, no engine names across the API, and action controls remain in Telegram/iMac chat until Phase 3.

Still intentionally not built: composer writes, approval buttons, Stop-all, run steering, artifact diff comments, and open-local-file buttons. Those need the internal MayaAppServer protocol and permission kernel, not ad-hoc UI POST routes.
