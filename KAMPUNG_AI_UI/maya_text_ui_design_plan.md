# Maya Text UI — Design Plan

Date: 2026-06-11
Design reference: `docs/design/taste_skill_reference.md` (Taste Skill, baseline dials adapted below)
Status: Plan — no code yet

## 1. What we are building

A local-first web chat UI for the Maya runtime — a third client alongside Telegram and iMac, talking to the same MayaLoop/thread manager. It is a chat surface plus the runtime context that makes Maya different from a chatbot: thread history, approval gates, artifact delivery, route/cost visibility, and agentic step traces.

Not in scope for v1: voice, screen control, Maya Desk metrics (stays a separate report), public/multi-user onboarding.

## 2. Design dials (Taste Skill baseline, adapted)

| Dial | Taste default | Maya UI | Why |
|---|---|---|---|
| DESIGN_VARIANCE | 8 | 6 | Chat is a utility surface; asymmetric chrome, but the thread column stays predictable |
| MOTION_INTENSITY | 6 | 5 | Streaming text + status dots provide life; no scroll choreography needed |
| VISUAL_DENSITY | 4 | 5–6 | Agent traces, costs, and approvals are data-dense; numbers in monospace |

## 3. Visual direction

**Aesthetic:** "Quiet workshop" — Vercel-core neutrality with one warm accent. Maya is a personal tool, not a SaaS landing page. No purple, no neon, no glow (LILA BAN applies).

- **Base palette:** Zinc. Light mode `#f9fafb` background, white surfaces with `border-zinc-200/60`. Dark mode `zinc-950` (never `#000`), surfaces `zinc-900`.
- **Single accent:** Deep emerald (`emerald-600` light / `emerald-500` dark), desaturated. Used only for: send action, Maya's active/streaming indicator, approval-granted states.
- **Semantic colors:** Amber for pending approvals, rose for errors/denials. Never decorative.
- **Typography:** `Geist` for UI and chat text, `Geist Mono` for costs, routes, token counts, event IDs, and all numbers. No Inter, no serif anywhere (this is a technical UI).
- **Surfaces:** Cards only where elevation means something (approval prompts, artifact previews). Everything else separated by `border-t` / `divide-y` and whitespace. Tinted diffusion shadows only.
- **No emojis** in chrome or system copy. Phosphor icons, `strokeWidth` 1.5 throughout.

## 4. Layout

Asymmetric three-zone desktop layout (`2fr 5fr 2fr` feel, not equal thirds), collapsing to single column below `md`:

```
+------------+----------------------------+--------------+
| Threads    | Conversation               | Run Context  |
| (rail)     |                            | (inspector)  |
+------------+----------------------------+--------------+
```

1. **Thread rail (left):** Persistent threads from MayaThreadManager. Each row: title, relative time, channel origin glyph (Telegram/desk/voice), unread dot (breathing animation when Maya is still working in that thread). No card boxes — `divide-y` rows.
2. **Conversation (center, max-w-[72ch] for text):**
   - User messages right-aligned, plain — no bubble fill, just a hairline left border accent.
   - Maya messages left-aligned with streaming typewriter rendering.
   - **Inline event blocks** between messages (collapsed by default): tool calls, plan steps from the agentic loop, permission checks. Rendered as monospace rows with status glyphs, expandable. This is the signature element — the chat shows the harness thinking, not just the answer.
   - **Approval prompts** are the one true card: elevated, amber-tinted border, Approve/Deny with tactile `scale-[0.98]` press, and an explicit scope line ("allow `office.write` for this thread").
   - **Artifact deliveries** as compact rows: file icon, name, species (Word/Excel/PPT/Blender), QA gate status, open-locally action.
3. **Run context inspector (right, collapsible):** Live route + model lane, running cost (monospace, organic numbers like `RM 0.0417`), memory writes this session, active permissions. Cockpit-style: 1px separators, no cards, `font-mono` numerals.

**Composer (bottom of center):** Single field, label-above pattern for attachments/options, slash-command hints, Enter to send. Subtle shimmer on the border while Maya is processing — no spinner.

## 5. Motion

- **Streaming text:** Token-by-token reveal, no fade-in per character (performance).
- **Message entry:** Spring (`stiffness: 100, damping: 20`), translate+opacity only.
- **Event blocks:** `layout` animation when expanding; stagger children at 60–80ms when a plan unfolds.
- **Status dots:** One perpetual breathing dot when Maya is active — isolated, memoized client component.
- **Approval card:** Overshoot spring on entry, must visually demand attention without sound.
- Everything animates via `transform`/`opacity` only. No scroll hijack. No magnetic buttons in v1 (utility surface).

## 6. Mandatory states (Taste Rule 5)

| Surface | Loading | Empty | Error |
|---|---|---|---|
| Thread rail | Skeleton rows matching layout | "No threads yet — say something to Maya" composed state | Inline retry row |
| Conversation | Shimmer skeleton sized like a Maya message | First-run welcome with 3 real example prompts (from actual skills: "Build me an Excel cashflow model", "Summarise this PDF", "Check my network config") | Inline error row with route info + retry; never a toast-only failure |
| Inspector | Skeleton metric lines | Hidden until first event | Stale-data badge with last-updated time |
| Approvals | n/a | n/a | Deny reason captured inline |

## 7. Stack recommendation

> **Council-revised (2026-06-11):** No Node/React build toolchain (unanimous). Phase 2 = FastAPI inside the harness, **read-only**: SSE out of the event store, zero POST/WebSocket endpoints until the internal MayaAppServer protocol is stable — this enforces the doctrine's deferral structurally, not by willpower. Phase 3 (interactive: approvals, steering, diff comments) = adopt **Preact + htm via CDN ESM** (~4KB, component state, still no build step) rather than scaling vanilla JS into coordinated bidirectional state. SSE over WebSocket confirmed for the feed; approval submissions are plain POSTs when Phase 3 opens.

The repo is Python; keep the UI dependency-light and local-first:

- **v1:** Vite + React + Tailwind v4 + Framer Motion + Phosphor icons. Single-page app served by a small FastAPI/uvicorn endpoint inside the harness (`maya_web.py`), WebSocket to MayaLoop for streaming and events. No Next.js — no SSR need for a local tool.
- Reuse the existing event store as the message source of truth; the UI is a renderer of events, which keeps it honest with the Telegram channel.
- shadcn/ui allowed only customized (radius, zinc palette, no default look).

## 8. Build phases

1. **Static mockup** — one HTML/React file, hardcoded thread + events, full visual language. Approve the look before wiring anything.
2. **Read-only client** — render real threads/events from the event store over WebSocket.
3. **Interactive** — composer, streaming, approvals round-trip through the permission kernel.
4. **Inspector + artifacts** — cost/route panel, artifact open-locally actions.
5. **Polish pass** — run the Taste pre-flight checklist (Section 10 of the reference) before calling it done.

## 9. Open decisions

- Dark-mode-first or light-mode-first? (Inspector cockpit reads better dark; recommend dark-first.)
- Does the web UI get its own channel ID in the allowlist model, or impersonate the desk channel?
- Should inline event blocks be on by default (transparent) or collapsed (calm)? Recommend collapsed with a per-thread toggle.


## 10. Locked build rules (2026-06-11, Zainal)

1. **Default theme is LIGHT.** Dark is opt-in via the toggle; the saved preference persists per machine.
2. **Code follows the Kampung AI rule:** max 300 logical lines per file (warning 250, urgent 280) — applied to the UI's Python AND its JS/CSS modules. No 400-line allowance.
3. **Change model:** the UI is a renderer over the append-only event store — it owns zero state of its own. Every tile is (event/state query → view). New features add a query + a view module; nothing migrates. New event types are additive; the UI ignores unknown types (tolerant reader). All visual identity lives in CSS variables, so retheming is a token swap. The read API (SSE + a few GETs) is the only contract the tabs know; when MayaAppServer stabilizes, it slots underneath without touching tab code.
4. **Scale model:** data scale = windowed queries + delta SSE + capped scrolling tiles (SQLite is fine to millions of rows locally). Feature scale = registry-driven surfaces (tools/skills/automations render from data, so new ones appear without UI edits). Interaction scale = Phase 3 Preact+htm. Remote access = serve over Tailscale, same single user. Multi-user is a product decision gated on the Phase 24 wedge question — explicitly NOT built for now.
5. The screenshot harness (playwright shoot.js) is kept as a UI render smoke for local CI once Phase 2 exists.

### Council amendments to the change & scale model (2026-06-11)

Verdict: **adopt with amendments.** Corrections to the advisor's claims: "zero UI state" is oversold — the UI owns no *domain* state, but ephemeral state (selection, scroll, theme, Phase-3 optimistic writes) is real and must be explicitly scoped as disposable. Registry-driven surfaces and pure-renderer doctrine are design principles to converge on, not day-one mandates. A screenshot smoke is a render gate, not a correctness gate for SSE ordering/backpressure.

Do NOW (before/with Phase 2):
1. Add a `schema_version` column to the event envelope (one ALTER TABLE, default 1) — retrofitting versioning onto a grown store is the expensive path. Tolerant-reader handles unknown types but not changed ones.
2. Write the one-page SSE protocol spec (cursor format, reconnect/resume, error envelope) before either side is built — two components agreeing on a wire format need a written contract.
3. Bearer token middleware before the UI is reachable over Tailscale — Tailscale narrows the network, it is not auth (~20 lines, token in .env).

DEFER (with explicit triggers):
4. Optimistic-write reconciliation contract → write it the week the first POST handler lands (Phase 3 start), not before.
5. Server-side projection registry → formalize when there are 3+ projections or query wiring gets copy-pasted; until then a {name: query_fn} dict in one module IS the registry.

House rule adopted: add architecture when the same change has to be made in three places — not before.


## 11. Full implementation roadmap (2026-06-11)

| Phase | Scope | Gate to exit |
| --- | --- | --- |
| 0 — Design (DONE) | 3 candidate designs → B2 expanded; 3 council rounds; Living Bamboo tokens; light default | councils scored 7.5/10, fixes applied |
| 1 — Design lock (WAITING) | In-browser check with real fonts (dark bubbles, type rhythm) | Zainal says "final" |
| 2 — Read-only live desk (BUILT) | SSE protocol v1 · token auth · lane masking · Desk/Conversation/Memory/Artifacts live against real store · zero writes | runs on the iMac without leaks or crashes |
| 2.5 — Proof cockpit hardening (BUILT, soak pending) | Proof tab from eval/demo/live/browser logs · Automations tab from routines/weekly/nightly runs · memory audit stream · artifact sessions/reviews · schema helper · launchd template · API smoke | `ui_read_api_smoke.py` passes; daily use confirms stability |
| 3 — Interactive (GATED on MayaAppServer internal protocol + Phase 24.6 validation green) | Preact+htm via CDN · POST approvals (yes/no through kernel) · run steering (pause/redirect/stop) · composer → send_message · Conversation tab becomes real chat with Desktop/Maya tree + artifact-session context chip · optimistic-write reconciliation contract written first | one live run approved + steered from the UI, kernel-gated, with trace evidence |
| 4 — Surface parity | Stop-all through the permission kernel · artifact diff view + comment→edit request · gate-decision feed · two-tier alerts mirrored to Telegram · open-local-file controls through approved bridge | every mockup tile backed by real data; no placeholders left |
| 5 — Hardening + access | projection registry (trigger: 3+ projections) · visual-regression renders in CI · 7-day UI soak alongside the runtime soak · Tailscale + phone access with token · perf pass on year-scale data | soak clean; phone usable |
| 6 — Futures (gated on the Phase-24 wedge decision) | live voice-session mirroring in chat · app packaging (Living Bamboo icon) · hosted or multi-user release = separate re-architecture, not a UI patch | product decision, not engineering |

Rules that hold across all phases: read-only until Phase 3 gate; 300 logical lines per file; engine names never cross the API; chat to act, UI to see; add architecture only when the same change hits three places.
