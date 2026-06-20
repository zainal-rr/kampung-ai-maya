# Maya / Kampung AI — Weakness Review (LLM Council Method)

*Compiled June 11, 2026. Method: Andrej Karpathy's LLM Council pattern applied as an analysis frame. Each weakness is examined by four council seats giving independent opinions, then the Chairman synthesizes a verdict. The council seats are mapped to Maya's real model lanes so the exercise mirrors how a governed Council lane would actually run inside her.*

## The Council

| Seat | Lane | Lens |
| --- | --- | --- |
| **The Architect** | Gemini | systems design, how the piece fits the harness |
| **The Planner** | GPT | sequencing, effort, what to do first |
| **The Contrarian** | Grok | blunt reality check — is this even a real problem? |
| **The Chairman** | Claude Steward | synthesis, risk gate, final verdict + severity |

Severity scale: 1 (cosmetic) → 5 (blocks everything else). Each verdict ends with a one-line directive.

---

## Weakness 1 — Thin agentic loop (opt-in, 8-step cap, verifier defaults to "yes")

**What it is.** The closed-loop reasoning runs only when `MAYA_AGENTIC_LOOP=1`, caps at `MAX_STEPS=8`, plans by asking a model for JSON instead of native function-calling, and `verify_goal` returns `True` on any error — so a broken verifier silently ends a run as "done."

**The Architect (Gemini).** The graph is sound; the intelligence on top of it is thin. The spine already supports loop edges, checkpoints, and per-step retrieval — what's missing is native tool-calling and a real verifier. This is an upgrade to existing nodes, not a rebuild.

**The Planner (GPT).** Sequence it: (1) flip the planner to native function-calling, (2) make every registry tool reachable instead of the 7 mapped ones, (3) fix the verifier to retry/reflect on failure rather than defaulting to satisfied, (4) only then raise the step budget. Raising the budget before fixing the verifier just buys more confidently-wrong loops.

**The Contrarian (Grok).** Honest question — does a personal assistant need 50-step autonomy? Most of Maya's value is 1–3 step tasks. The risk isn't "too shallow," it's that you'll chase frontier-agent depth you don't need and add failure surface. Fix the verifier, lift the cap modestly, stop there.

**Chairman verdict — severity 4.** The loop is the single biggest capability gap, but the Contrarian is right that the goal is *reliable* autonomy, not *maximal* autonomy. The verifier-defaults-to-yes behavior is the real defect — it converts the safety-favoring default into a correctness bug. Fix verification first, native tool-calling second, deeper budgets last. **Directive: fix `verify_goal` to fail-closed with one reflective retry before anything else.**

---

## Weakness 2 — Lexical memory, embeddings off by default

**What it is.** Recall matches tokens; the embedding rerank is gated behind `MEMORY_EMBED_RERANK_LIVE=1` and only reranks candidates that already have lexical/FTS evidence. Paraphrases and Malay↔English recall fail out of the box. No entity linking; upsert overwrites instead of superseding.

**The Architect (Gemini).** The machinery exists and is unused. The rerank is cached and fail-open, so always-on costs little. The nightly-consolidation + `memory_links` work already adds association and semantic dedup — wire those into retrieval and the picture changes overnight.

**The Planner (GPT).** Three steps, ascending effort: (1) flip embedding rerank always-on, (2) add the one-line `expand_with_neighbors` boost into `search_relevant_canonical_memories`, (3) change upsert to supersede-not-overwrite for temporal recall. The first is a config flip with immediate recall gains.

**The Contrarian (Grok).** Don't oversell entity graphs. For one user with a few hundred facts, you don't need Zep. You need recall@1 to stop being near-zero on paraphrases. The cheap fixes get you 90% of the value; the graph is a vanity feature until you have the users to justify it.

**Chairman verdict — severity 3.** Real gap, but the cheapest fixes close most of it, and the groundwork is already written and smoke-proven. This is the highest *value-per-effort* item on the board. **Directive: ship always-on rerank + neighbor boost this week; defer the entity graph until multi-user.**

---

## Weakness 3 — Single-user, hardwired to Zainal's life

**What it is.** Telegram allowlist, Omi, Mudra, the iMac, Ara, personal constants — Maya is welded to one person. No multi-user thread isolation, no per-user permissions, no onboarding.

**The Architect (Gemini).** The thread manager already namespaces identities (`maya:telegram`, `maya:project:*`). Multi-user is mostly threading a `user_id` through the memory and permission layers — non-trivial but not architectural surgery. The hard part is the personal constants scattered across files.

**The Planner (GPT).** Don't multi-user yet. First extract personal config (keys, IDs, device names) into one config file. That single move makes Maya *cloneable* — a second person could run their own instance before you ever build true multi-tenancy. Multi-user-in-one-instance is a later, bigger decision.

**The Contrarian (Grok).** This is only a weakness if you want other users. As a personal agent for Zainal, it's a feature — the tight coupling is why she's good. Decide the goal before "fixing" this. If it stays personal, this drops off the list entirely.

**Chairman verdict — severity 3 (conditional).** Severity depends entirely on intent. If Maya stays personal, this is a 1. If she's meant for others, it's a 4 and it gates every Opportunity. The Planner's "cloneable before multi-tenant" path de-risks the decision cheaply. **Directive: extract personal config into one file now (useful either way); defer true multi-user until the goal is decided.**

---

## Weakness 4 — ~660 flat root files, hard to hand off

**What it is.** The repo root holds hundreds of Python files (a large fraction `*_smoke.py`), governed by a 300-line cap, with no package structure or `tests/` tree.

**The Architect (Gemini).** The 300-line cap created breadth instead of depth — many small files rather than a few cohesive modules. It's navigable for the author and opaque to everyone else. Group into packages (`memory/`, `harness/`, `browser/`, `documents/`) and move smokes to `tests/`. Mechanical, low-risk, high-payoff.

**The Planner (GPT).** This is the gating item for *reach*. None of the Opportunities (Council product, memory-as-product, contributors) are reachable until a second person can find their way around. Do it before, not after, any growth push. Start with a `tests/` move — pure win, zero logic change.

**The Contrarian (Grok).** It works and it's tested, so this is debt, not damage. But it's the debt that quietly kills the project the day you want help. The bus factor is one. That's the actual risk here, not aesthetics.

**Chairman verdict — severity 4.** Not a runtime danger, but the structural barrier to every external ambition and the single-maintainer bus-factor risk. The Contrarian names the real stake: it's fine until the day it's fatal. **Directive: restructure into packages + `tests/` before any distribution work; this gates the Opportunity column.**

---

## Weakness 5 — Plaintext credentials, host execution

**What it is.** Provider keys live in `.env`; tools execute directly on the iMac with no sandbox. Maya's hard-block protects *outputs* (she won't print secrets) but doesn't encrypt keys at rest — an infostealer on the machine lifts a working clone, the same failure mode that made OpenClaw a nightmare.

**The Architect (Gemini).** Two separable problems. Credentials-at-rest: hand off to the macOS Keychain instead of `.env` — modest, well-trodden. Sandboxing tool execution: much larger, touches every tool router. Treat them independently.

**The Planner (GPT).** Credentials first — it's the cheap, high-impact half and directly closes the OpenClaw-class risk. Sandboxing is a bigger project; stage it (start with the highest-blast-radius tools: repo writes, shell, browser). Also add the missing piece: run browser/Omi/screen *input* through the sensitive-info filter, so prompt-injection can't widen permission scope.

**The Contrarian (Grok).** For a single local machine that's yours, this is lower urgency than it looks — there's no exposed gateway like OpenClaw's. It becomes urgent the moment Maya runs for anyone else or on a server. Right risk, possibly wrong timing.

**Chairman verdict — severity 4 (latent).** Low probability today, severe impact, and it's the exact mechanism behind the category's worst incidents. The Contrarian is right on timing but the Planner's credential fix is cheap enough to just do. **Directive: move keys to Keychain now; filter read-surfaces against injection; stage sandboxing before any non-personal deployment.**

---

## Weakness 6 — macOS-only AppleScript browser control

**What it is.** Browser actions drive Chrome via AppleScript (with an extension-bridge fallback), making the browser lane macOS-only and fragile versus the CDP/Playwright control everyone else uses.

**The Architect (Gemini).** AppleScript is brittle and platform-locked, but the driver is already abstracted (`make_browser_controller`) and the extension bridge points the right way. Migrating to a CDP/Playwright driver behind the same interface is contained — the rest of the system doesn't need to know.

**The Planner (GPT).** Low priority relative to 1, 2, and 4. Do it when browser reliability becomes the bottleneck or when you need cross-platform. Until then, the extension bridge is good enough. Don't pay this cost early.

**The Contrarian (Grok).** This only matters if browsing is core to Maya's value. If she's mostly memory + documents + chat, the browser lane is a side feature and AppleScript-fragility is a footnote. Rank it by how much you actually browse.

**Chairman verdict — severity 2.** Real but contained, well-abstracted, and low on the priority order. A platform/reliability ceiling, not a present danger. **Directive: migrate to a CDP/Playwright driver when browsing becomes core or cross-platform is needed — not before.**

---

## Chairman's Compiled Verdict

The council converges on one theme: **Maya's weaknesses split cleanly into "capability/reach" (real, worth fixing) and "danger" (mostly latent, cheaply contained).** Nothing here is an active fire. The work is to raise the ceiling, in this order:

| # | Weakness | Severity | Effort | Priority | First action |
| --- | --- | :---: | :---: | :---: | --- |
| 1 | Thin agentic loop | 4 | Med | **1** | Fix `verify_goal` to fail-closed + retry |
| 4 | Flat 660-file codebase | 4 | Med | **2** | Move smokes to `tests/`, then package |
| 2 | Lexical memory | 3 | Low | **3** | Always-on rerank + neighbor boost |
| 5 | Plaintext creds / no sandbox | 4* | Low→High | **4** | Keys → Keychain; filter read-surfaces |
| 3 | Single-user wiring | 3* | Med | **5** | Extract personal config to one file |
| 6 | AppleScript browser | 2 | Med | **6** | Defer to CDP/Playwright when needed |

\* latent / conditional on intent.

**The two cheapest high-value moves** (memory rerank flip, credentials→Keychain) should happen first regardless of strategy — days of work, immediate gains. **The two gating moves** (verifier fix, codebase restructure) unlock everything above them: the verifier gates trustworthy autonomy, the restructure gates every external ambition. **The two conditional moves** (multi-user, browser) wait on a single decision: *is Maya staying personal, or going to other people?* Answer that, and the bottom half of the list either disappears or jumps to the top.

One closing note from the Chairman, consistent with the whole review: every directive above preserves Maya's defining property — the governance shell. None of these fixes trade auditability or the forget guarantees for capability. That constraint is the point.
