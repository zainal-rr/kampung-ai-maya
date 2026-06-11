# Kampung AI Architecture

Kampung AI is a local-first personal agent harness. Maya is the user-facing identity. The runtime underneath manages persistent threads, event traces, model lanes, skills, permissions, memory, artifacts, local computer actions, and resumable workflows across Telegram, iMac, voice, screen, browser, Office documents, app projects, and Blender/Maker work.

This file is the concise architecture source. Execution state lives in `KAMPUNG_AI_CHECKLIST.md`. Detailed private operating rules live in `docs/maya_operating_doctrine.md`. Public/investor explanation lives in `README.md` and `docs/public_architecture.md`.

## Documentation Map

| File | Purpose |
| --- | --- |
| `README.md` | Public technical overview, demos, safety model, verification commands, known limitations |
| `KAMPUNG_AI.md` | Concise canonical architecture and system boundaries |
| `KAMPUNG_AI_FULL.md` | Long-form architecture, doctrine, preferences, historical decisions, and detailed operating rules |
| `KAMPUNG_AI_CHECKLIST.md` | Single roadmap and execution checklist source of truth |
| `docs/public_architecture.md` | Public/investor architecture narrative without private doctrine clutter |
| `docs/proof_and_readiness.md` | Proof state, evidence boundaries, scores, and remaining validation |
| `docs/maya_operating_doctrine.md` | Private doctrine copy kept under `docs/` for document separation |

## Core Category

Kampung AI is not just:

1. A Telegram bot.
2. A model router.
3. A LangGraph workflow set.
4. A document generator.

It is a personal agent runtime with:

1. Persistent threads.
2. Event-sourced workflow traces.
3. Tool registry and permission checks.
4. Canonical memory.
5. Artifact quality gates.
6. Skills and review standards.
7. Channel-specific delivery.
8. Resumable background work.

## Maya Runtime Loop

The canonical Maya loop is:

1. Receive input from Telegram, iMac voice, screen, browser, or a scheduled job.
2. Load thread state and recent context.
3. Classify intent semantically.
4. Select the lane, skill, and workflow type.
5. Check permissions before any side effect.
6. Execute local tools, model calls, browser work, Office builders, or Artisan jobs.
7. Observe and verify the result.
8. Record events and artifacts.
9. Update memory only when allowed.
10. Deliver through the active channel.
11. Pause, resume, or finish the workflow.

## Harness Spine

The newer harness spine is the architecture target:

| Component | Role |
| --- | --- |
| `MayaThreadManager` | Owns thread identities such as `maya:telegram`, `maya:imac`, project threads, and weekly-memory background threads |
| `MayaEventStore` | Records important events: user messages, route decisions, tool calls, approvals, artifacts, memory writes, pauses, resumes, and failures |
| `MayaToolRegistry` | Declares tools with input schema, output schema, permission scope, side-effect level, cost risk, and replay safety |
| `MayaPermissionKernel` | Decides allow, confirm, deny, or hard-block before side effects |
| `MayaHarnessSDK` | Provides the local facade for start thread, send message, call tool, request approval, create artifact, write memory, and resume thread |
| `Maya Desk` | Local audit cockpit for routes, costs, workflows, approvals, artifacts, evals, provider readiness, and live-proof boundaries |

Retired coding-provider architecture and alternate deep-routing paths must not return. `legacy_architecture_removed_smoke.py` enforces this in local CI.

## Model Lanes

| Lane | Responsibility |
| --- | --- |
| Gemini | Normal Telegram text, artifact preflight, drafting, sight, memory shaping, source-aware research, and image generation when enabled |
| Claude | Steward review for Office artifacts, workflows, self-heal proposals, safety, and quality checks |
| GPT complex lane | `/complex` planning, high-complexity reasoning, and decision-ready repair plans |
| xAI/Grok/Ara | Live voice presence, Telegram voice-note STT, Ara voice notes, current/news lane |
| Artisan | Codex-backed local implementation lane for repo work, app building, tests, self-heal patches, and Blender/Maker source generation |

The lane name is still Artisan. Codex is the implementation engine behind it. Word, Excel, PowerPoint, memory, normal chat, voice presence, and document review do not move to Artisan.

## Channel Rules

| Channel | Role |
| --- | --- |
| Telegram | Remote text, photo, voice-note, file delivery, route/cost audit, document follow-up, memory commands, `/complex`. Closed by default: only chat ids in `TELEGRAM_ALLOWED_CHAT_IDS` are answered; all other senders are rejected and logged. |
| iMac voice | Primary local conversational body, short answers, live status, and in-session starts for longer Maya work |
| Mudra Link | Pass-through local input only: Mudra Link Mouse Mode may send existing iMac hotkeys, with Twist mapped to `Option + Space` and Double Twist mapped to `Option + Escape`. Maya has no active Mudra adapter, SDK listener, or gesture runtime. |
| Screen sight | One-shot active-screen context when explicitly active or when local iMac voice asks for visible context |
| Browser | Local Chrome inspection, safe clicking/filling, travel comparison, YouTube/research workflows, and verification after actions |
| Background runtime | Scheduled weekly memory, reminders, self-heal proposals, in-session voice work results, and workflow continuation |

Telegram and iMac share the same memory, artifact, workflow desk, and document quality architecture. Delivery differs by channel only.

Telegram has an explicit conversation contract: greeting-only messages get a warm short acknowledgement; stale pending artifact/session state is cleaned before routing; normal model chat may not claim files, attachments, browser actions, or memory writes unless a verified tool or delivery path actually did the work. Strong artifact requests that hit a tool failure must return an honest failure instead of falling through to normal chat.

## Artifact Quality

Model text is not the final artifact. Real artifacts are created through local file builders, validated locally, reviewed when useful, repaired when possible, and delivered only with honest status.

| Artifact | Quality contract |
| --- | --- |
| Word | Scenario-specific structure, useful headings, real content, no filler, no malformed markdown, local `.docx` validation, visual QA, Claude review |
| Excel | Domain-specific rows, formulas, totals, formatting, notes/source columns when useful, pastel headers only, local workbook validation |
| PowerPoint | Dark/editorial default unless asked otherwise, short visible slide text, speaker notes, images where useful, aspect-ratio checks, render QA, Claude review |
| HTML/app | Project-folder workflow for serious apps, valid HTML/CSS/JS, browser smoke where possible, local QA, review/repair |

Document species decide the shape before the model writes. Word intents
(`word_quality.py`) cover proposals, technical guides, itineraries with exact
Day 1..N coverage, checklists, SOPs, workshop plans, investor briefs, and
strategy docs. Excel species (`excel_species.py`) give domain trackers,
content calendars, research logs, inventories, dev trackers, and formula-driven
financial models their own schemas instead of one shared skeleton. Deck
species (`deck_species.py`) select both the narrative arc (travel, technical,
teaching, review, pitch, issue/awareness) and a species visual identity
(`office_pptx_palette.py`): accent system, layout rhythm, and species-tinted
backgrounds within the dark and pastel families. All species routing is
deterministic and replay-safe; `document_species_smoke.py` pins it with real
prompt shapes.

Natural follow-ups update the latest active artifact in place unless the user asks for a new version. If QA fails, Maya restores the original and reports that the update failed instead of sending a rejected artifact as final.

## Memory Model

Canonical memory is the truth layer. Preferences, lessons, curated memory, session search, and compacted summaries are views or indexes, not separate truth stores.

Core rules:

1. Save explicit memories only after write and read-back verification.
2. Recall direct memory questions from canonical memory first.
3. Forget must invalidate canonical and derived traces.
4. Forgotten facts must not leak back from raw session history.
5. Temporary test memories must not become long-term profile memory.
6. Weekly memory reads canonical memory and selected summaries, excludes temporary test facts, and never recreates forgotten facts.
7. Weekly provider failures degrade safely: if Claude review is unavailable, Maya may save the conservative weekly summary but must save zero unreviewed canonical facts and audit the reviewer error.
8. Memory time audit is append-only evidence, not a second truth store. Canonical writes, updates, forgets, recalls, activations, weekly candidates, weekly saves/rejects, and leak checks write redacted audit rows with content hashes.
9. Memory canaries are long-term trust probes for active, forgotten, temporary, project, and pinned memory. Canary checks must prove forgotten values do not leak through canonical active rows, preferences, lessons, raw history, session search, summaries, weekly summaries, or curated memory.

Maya Desk and `/memory inspect` surface recent audit events and canary status so memory drift is visible instead of silently accumulating.

## Domain Knowledge Packs

Skills can carry knowledge bases. Any skill file in `maya_skills/active/` with
a `## Knowledge Base` section becomes a domain pack: its trigger phrases are
the routing configuration, and `domain_knowledge.py` retrieves matching
content from the pack's docs tree into the prompt (deterministic lexical
retrieval, word-boundary triggers, phrase vetoes, whole-recipe retrieval for
anything under `recipes/`, hard token budget, and silence when nothing clears
the minimum-overlap bar). Retrieval activations are logged to the skill usage
store as `domain:<skill_id>`.

Current packs: `network_engineering` (`docs/networking/`: architecture,
protocols, IOS-XE recipes) and `finance_credit_analysis` (`docs/finance/`:
credit/liquidity/earnings concepts plus worked analysis recipes with explicit
formulas). Adding a new domain requires no code: one skill file plus a docs
tree following the pack's recipe contract. Proposed packs stay inert until
promoted to `maya_skills/active/`.

## In-Session Voice Work

xAI voice is Maya's live spoken presence. Longer spoken requests start Maya's local work during the same voice session instead of waiting for the microphone to close. Maya acknowledges quickly, starts the work in the background, keeps the voice session available for interruption and status checks, then speaks the result if the mic is still open. Browser work routes through `browser_capability`; document, memory, coding, and project work route through Maya's local workflow layer. If the mic closes first, the result remains recorded for later recall.

Voice transcript cleanup removes filler words, repeated starts, self-corrections, and cut-off artifacts without rewriting the user's intent. The cleanup layer is an adapter; it must not bypass semantic routing, safety, memory, approval, or artifact QA.

## Browser And Travel Safety

Maya may search, compare, summarize, and fill non-sensitive filters. She must stop before booking, payment, checkout, upload, login submission, passport, OTP, card, bank, private identifier, or final submit actions unless an explicit staged approval flow is completed. Secrets and sensitive private data remain hard-blocked.

Browser actions require verification: visible text, URL, title, target presence, modal state, or screenshot/DOM evidence where available. Clicks without verification are not considered complete.

Travel research can feed the budget layer. When Maya opens or selects a visible priced Google Flights, Booking.com, or Airbnb option, she records the chosen provider, option text, and MYR price into `maya_travel_plan`; travel budget workbooks then place those saved values in the selected flight/stay rows and budget snapshot. Spoken or typed prices still work, but browser selection is now a first-class capture path.

## Agentic Workflow

`/complex` is the entry point for serious agentic workflows. The expected chain is:

1. Plan.
2. Claude review.
3. Durable harness run.
4. Approval when action is needed.
5. Checkpointed execution.
6. Verification.
7. Repair or rollback when needed.
8. Final report.

Self-healing is the first priority target because it directly improves reliability. `/complex self heal Maya after approval` creates a checkpointed run with `diagnose`, `snapshot`, `plan_patch`, `await_approval`, `apply_patch_isolated`, `verify`, `repair_once`, `final_report`, and `failed` states. Snapshot is mandatory before mutation. Memory-only self-heal writes rollback snapshots; isolated repair work pauses for a second approval before mutation. Repo changes, deployment, restart, broad refactors, destructive operations, and apply-back from isolated worktrees still require explicit approval.

The harness graph also supports an opt-in agentic loop (`MAYA_AGENTIC_LOOP=1`
plus the GPT planner from `assistant_model_lanes.build_harness_planner`).
When active, runs iterate plan → execute → verify within a hard budget of 8
steps: the planner proposes the next tool call or declares the goal done
(`harness_llm_planner.py`), the permission kernel gates every proposed tool
(deny → honest refusal, sensitive → the normal approval pause), domain
knowledge is re-retrieved per step, and the trace records `loop_iteration`,
`agentic_action`, and `domain_knowledge` events. With the flag off (default)
the graph is byte-identical to the single-pass behavior.
`harness_agentic_deep_smoke.py` pins all three paths deterministically.

## Safety Boundary

| Action | Default |
| --- | --- |
| Local artifact creation inside Maya workspace | Allowed when requested, then QA checked |
| Repo patch/apply-back | Approval required |
| Commit, push, deploy, restart | Approval required |
| Delete files/resources | Approval required |
| External send/upload/share | Approval required |
| Booking, purchase, payment, submit | Approval required |
| Passwords, API keys, private keys, OTP, bank/card data | Hard blocked |
| Slicing/uploading/physical 3D print | Approval required |

## Proof Boundary

Local CI and deterministic replays are strong software proof. They do not replace physical iMac voice, real live billing/session behavior, real elapsed 30-day reliability, Omi/Mudra hardware, or physical printer proof.

Current conservative operational estimate:

| Area | Estimate |
| --- | ---: |
| Telegram | 92% |
| Document creation | 90% |
| Memory architecture | 87% |
| Weekly memory automation | 85% |
| Browser/agent workflow | 90-92% |
| Agentic workflow | 82% |
| Hardware/Blender/Maker | 65-70% |
| Overall Kampung AI | 84-86% |

Use `docs/proof_and_readiness.md` and Maya Desk for detailed proof status.

## Engineering Discipline

1. Root Python files should not exceed 300 lines.
2. Files in the 280 to 300 line range are urgent refactor candidates.
3. `local_ci.py` is the default no-provider proof command.
4. `code_health.py` is blocking in local CI.
5. Retired architecture markers are blocked by `legacy_architecture_removed_smoke.py`.
6. New features must have tests or explicit live-proof boundaries.
7. Public proof must not expose secrets, raw private memory, or unnecessary private paths.

## Verification Commands

```bash
./venv/bin/python local_ci.py
./venv/bin/python legacy_architecture_removed_smoke.py
./venv/bin/python browser_multistep_live_probe.py
```

The live browser probe uses the local browser controller and user Chrome context. It should be run deliberately, not inside no-provider CI.
