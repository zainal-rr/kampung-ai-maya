# Maya Text UI — Complete Requirements

Date: 2026-06-11
Sources read in full: `KAMPUNG_AI.md`, `KAMPUNG_AI_FULL.md`, `KAMPUNG_AI_CHECKLIST.md` (Phases 1–25), `docs/maya_operating_doctrine.md`, `docs/public_architecture.md`, `docs/proof_and_readiness.md`, `README.md`.

## 0. Positioning constraint (from doctrine)

The doctrine is explicit: "Maya does not need a visible iMac UI... any future on-screen interface is optional and should be treated as debug or maintenance tooling, not the primary experience." So this UI is a **third client of the same runtime** (like Telegram and iMac voice) plus a **living replacement for the static Maya Desk HTML report** — not Maya's primary body. It must reuse `DocumentActionRouter`, the artifact session store, canonical memory, and the harness; channel-specific delivery only.

## 1. Identity rules the UI must obey

- **One Maya.** The user only ever meets Maya. **No provider/model names anywhere** in the UI. Lanes use the masked team names from doctrine: **The Sight** (drafting, research, vision), **The Mind** (explicit complex planning), **The Steward** (review/critique/safety), **The Artisan** (implementation, apps, maker), **The Pulse** (voice, current/news).
- **Brand: Living Bamboo.** Green bamboo, sparse leaves, three warm gold signal nodes. Banned: robot heads, chat bubbles as branding, AI brains, neon cyber motifs, purple gradients, circuit-board styling. Logo source: `assets/brand/kampung-ai-living-bamboo.png`.
- **Tone.** Warm, direct, lightly playful, never corporate. Replies start with the answer. No "status report" phrasing in chat. Structured answers use `1)` / `a)` style; stories flow as prose. Language mirroring (English ↔ Malay/Manglish). No emojis in chrome.
- **Honesty surface.** The UI must never show "done" without verified evidence: chat cannot claim files/attachments/browser work/memory writes unless a verified tool or delivery path did the work (June 10 conversation contract). Drafts that fail QA are labeled "draft with issues," never final.

## 2. Conversation surface

- Persistent **threads** from MayaThreadManager: `maya:telegram`, `maya:imac`, `maya:screen`, `maya:voice`, `maya:project:<slug>`, `maya:background:weekly-memory`, `harness:<run_id>`, `harness:background:<task_id>`. Show channel origin and busy state.
- Short **recent-topic window** with explicit `new topic` reset (must not clear the active project).
- Message types: text, photo with caption, voice-note transcript, file delivery, route records.
- **Conversational confirmations**: doctrine forbids button-only approvals — plain `yes`, `no`, `later`, `cancel` typed in chat must resolve the latest pending action; buttons may exist but only as accelerators for the same path. "No pending" answers locally when nothing is waiting.
- Greeting-only turns get a warm short acknowledgement. Wake-name prefix `Maya,` tolerated.
- Slash commands mirrored from Telegram: `/help /status /imac /see /screen /project /memory /complex` visible; others as hidden aliases. Natural language is primary.
- Quiet mode toggle; briefings arrive conversationally (morning briefing, evening recap, Sunday reflection).

## 3. Agentic work surface (workflow desk)

- **Harness states** as first-class visuals: `planning, executing, observing, verifying, waiting_approval, waiting_user, completed, failed, cancelled`.
- `/complex` chain rendering: plan → Steward review → approval → checkpointed run → verification → repair/rollback → final report. Bounded subagent fan-out (2–4 research subagents) shown as one merged step, not noise.
- **Agentic loop** (opt-in, 8-step budget): per-step trace with `loop_iteration`, `agentic_action`, `domain_knowledge` events; budget meter.
- **Self-heal runs**: `diagnose, snapshot, plan_patch, await_approval, apply_patch_isolated, verify, repair_once, final_report, failed`; snapshot-before-mutation indicator; second-approval pause; rollback armed status.
- Resume answers: "what are you working on", "where did we stop", "what is pending", continue / close workflow; numbered choice when several runs are active.
- Managed parallelism: background runs each with `run_id`, status, channel, project scope, owner lane; only one iMac-body workflow at a time.
- Replay safety: idempotency-ledger awareness — resumed actions show "verified, not re-run" instead of duplicate effects.

## 4. Approvals surface

- **Approval inbox** aggregation (everyday layer) + inline approval cards in chat.
- Show: tool, permission scope, side-effect level, cost risk, replay safety from MayaToolRegistry; allow / confirm / deny / hard-block outcome from MayaPermissionKernel.
- **Staged approvals**: travel flow (compare → choose exact option → final confirmation); self-heal second approval before isolated mutation; apply-back as a separate explicit action.
- Hard-block surface: secrets, OTP, bank/card, passport, private keys never render as approvable — show the refusal.

## 5. Artifact surface

- **Active artifact session** (24 h lifetime, shared across channels): type, path, short name, topic, structured state, revision count, status, expiry. Follow-up edits show the delta ("duration 2 → 4 days") and QA against the new intended state.
- **Species visibility**: Word intents (itinerary with Day 1..N, proposal, technical guide, SOP, investor brief...), Excel species (financial model, content calendar, inventory, dev tracker...), deck species (arc + visual identity). Short filenames (`kazakhstan-itinerary-v3.docx`).
- **QA gates** per artifact: local validation, visual QA, Steward review, repair attempts (bounded caps), polish grade for decks (draft-level/good/strong), structured issues (severity: blocker/warning/info; class: mechanical/open_world/semantic), QA disagreement events.
- Latest-document continuity: "where is it", "open the last document", "send it again"; open-locally action (Word/Excel/PowerPoint/Cursor).
- Maker artifacts: `.blend`/`.stl`/README/preview with dimensions and print-safety status, stopping before slice/upload/print.

## 6. Memory surface

- **Canonical memory inspector** (`/memory inspect`): memory IDs, subject keys, kind, scope, activation class (pinned / active / session / archive / temporary / forgotten), flags, reinforcement count, confidence, timestamps, redacted previews. Pin/unpin controls.
- **Memory time audit**: append-only event stream (canonical_write, update, forget, recall, activation, weekly_candidate, weekly_save, weekly_reject, leak_check) with redacted previews and hashes.
- **Canaries**: active, forgotten, temporary, project, pinned probes with leak status — drift must be visible.
- **Weekly memory**: user-facing `/weekly` view (clean takeaways, priorities, open loops — no raw paths, JSON, canonical IDs) strictly separated from `/weekly status` audit view (run rows, trigger source, provider counts, saved/rejected, reviewer fallback warnings).
- **Retention**: 90-day project/task retention states with 7-day deletion warnings surfaced in status/desk.
- Curated memory saturation (core 2477 / profile 1499 char caps) with usage %; self-heal dry-run entry point.
- Forget UX: forget resolves subjects, shows derived-trace cleanup, and the next recall honestly says "not saved."

## 7. Route, cost, and audit surface

- `/route`: last routing decision — input type, lane (masked name), reason, cost flag, timestamp; must not overwrite the route it inspects.
- `/cost`: local ledger by lane (voice minutes, TTS characters, STT seconds, sight calls, premium calls, implementation jobs, complex calls, review calls) in MYR.
- Telegram command audit, delivery audit, turn audit visibility for debugging.

## 8. Skills, knowledge, and extensibility surface

- **Skill lifecycle**: draft → proposed → approved → active → disabled; activation gate test results; only active skills shape behavior.
- Skill usage learning: outcomes, failures, corrections, improvement proposals; weekly skill review summaries.
- **Domain knowledge packs**: `domain:<skill_id>` activations (network_engineering, finance_credit_analysis), retrieval shown in traces; proposed packs visibly inert.
- Security manifests per skill/MCP tool; MCP registry states (proposed/approved/enabled/disabled).

## 9. Proof and health surface (Maya Desk successor)

- Conservative scores by subsystem (Telegram 92%, documents 90%, memory 85–87%, weekly 85–90%, browser 90–92%, agentic 78–83%, hardware 65–70%, overall 84–86%).
- **Proof separation** (non-negotiable per Phase 22): deterministic proof (local CI 34 checks, scored evals 25/25, replay suites 500/700/10000) vs live evidence (browser nights: night2 95%, night3-rerun 91.7%, night4 96.7%, 10/10 safety stops) vs `manual-live-required` (iMac long-work voice, Omi, Mudra, printer) vs pending (7-day soak, 30-day scorecard).
- Dependency readiness, heartbeat, launchd status, recent failures, trace metrics, proof-boundary snapshot.
- Autonomy mode display (`observe / suggest / auto_safe / full`, default auto_safe).

## 10. Safety boundary (always visible logic)

| Action | UI behavior |
| --- | --- |
| Local artifact creation in Maya workspace | proceeds, then shows QA |
| Repo apply-back, commit, deploy, restart | approval card, separate explicit apply-back |
| Delete, external send/upload/share | approval card |
| Booking, payment, checkout, submit | staged approval flow |
| Secrets, OTP, bank/card, passport, keys | hard-block notice, never approvable |
| Slicing, printer upload, physical print | approval card with safety status |

## 11. Explicitly out of scope (doctrine: do not add yet)

More models, WhatsApp, commercial onboarding, cloud deployment, multi-user permissions, public JSON-RPC server (internal protocol first), call mode, always-on voice. The UI consumes the internal SDK facade (`maya_harness_sdk.py`); a local WebSocket bridge comes only after the internal protocol is stable.
