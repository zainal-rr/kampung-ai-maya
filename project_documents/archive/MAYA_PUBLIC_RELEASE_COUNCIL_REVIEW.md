# Maya / Kampung AI — Weakness Review v2 (Public-Release Lens)

*Compiled June 11, 2026. Supersedes the first council review. Method unchanged: Karpathy's LLM Council — four seats give independent opinions, the Chairman synthesizes. What changed are the two facts the council was given:*

> **New fact 1 — Maya stays personal for now, but public release is a stated future goal.**
> **New fact 2 — The browser lane is used heavily.**

These two facts don't add weaknesses so much as **re-weight the whole board.** The two items the first review parked as "conditional" (single-user wiring, credentials/sandbox) are now hard blockers, because "public" means other people's data, other people's keys, and untrusted input at scale. And the browser — previously a severity-2 footnote — is now simultaneously your most-used capability *and*, at public scale, your single largest attack surface. The council also surfaces two weaknesses that only exist once you go public.

## The Council

| Seat | Lane | Lens |
| --- | --- | --- |
| **The Architect** | Gemini | systems design, how the piece fits the harness |
| **The Planner** | GPT | sequencing, effort, what to do first |
| **The Contrarian** | Grok | blunt reality check |
| **The Chairman** | Claude Steward | synthesis, risk gate, final verdict + severity |

Severity 1 (cosmetic) → 5 (hard blocker for public release).

---

## Weakness 1 — Thin agentic loop (opt-in, 8-step cap, verifier defaults to "yes")

**The Architect (Gemini).** Same structural fix as before — native function-calling, real verifier — but public release raises the stakes: untrusted users will invoke the loop, so a verifier that defaults to "satisfied" on error is now a *safety* defect, not just a correctness one.

**The Planner (GPT).** Order is unchanged: fix `verify_goal` to fail-closed first, then native tool-calling, then budget. But pull it earlier in the timeline — you don't want to ship autonomy to strangers on top of a verifier that can't tell when it failed.

**The Contrarian (Grok).** Still true that you don't need 50-step depth. But "public + autonomous + weak verifier" is precisely the combination regulators and CISOs point at. Keep the loop modest, make the verifier honest, and you sidestep the scary version.

**Chairman verdict — severity 4 (was 4).** Unchanged severity, higher urgency. The fail-closed verifier moves from "do first among capability work" to "do before any external user touches the loop." **Directive: fix `verify_goal` to fail-closed + one reflective retry; gate any public autonomy behind it.**

---

## Weakness 2 — Lexical memory, embeddings off by default

**The Architect (Gemini).** Public release makes the multilingual gap matter more — a public/SEA audience will hit the Malay↔English recall failure constantly. The always-on rerank is multilingual by design; flipping it is still cheap and now serves a real audience.

**The Planner (GPT).** Same three steps (always-on rerank → neighbor boost → supersede-not-overwrite). The entity graph stays deferred, but note: at multi-user scale, retrieval quality becomes a product differentiator, not a personal nicety.

**The Contrarian (Grok).** Don't let "public" tempt you into building Zep. For a public v1, recall@1 on paraphrases and two languages is the bar. The cheap fixes clear it.

**Chairman verdict — severity 3 (was 3).** Unchanged, still the best value-per-effort item, now with a clearer payoff. **Directive: ship always-on rerank + neighbor boost regardless of timeline; it helps you today and the audience later.**

---

## Weakness 3 — Single-user, hardwired to one person  →  now: multi-tenant readiness

**The Architect (Gemini).** This stops being "wiring" and becomes "isolation." The thread manager namespaces identities, but memory, audit, permissions, and artifacts all assume one human. Public release means a `user_id` (or tenant boundary) threaded through every read and write — and proof that user A's memory can never surface for user B.

**The Planner (GPT).** Two stages. Now: extract personal constants (keys, chat IDs, device names) into one config so Maya is *cloneable* — useful immediately. Pre-public: real per-user isolation with tests. Don't attempt multi-tenant-in-one-process until you've decided self-host-per-user (each runs their own) vs. hosted-multi-tenant (you run one for many). The first is far safer to ship and matches Maya's local-first DNA.

**The Contrarian (Grok).** Self-hosted-per-user is the answer, and it dodges 80% of this. If every user runs their own Maya, "multi-tenant isolation" mostly evaporates — you ship a clean single-tenant app that each person installs. Don't build a SaaS you don't want to operate.

**Chairman verdict — severity 5 (was 3, conditional).** Now a hard blocker — but the Contrarian narrows it: choose **self-host-per-user** and this drops from "build multi-tenancy" to "make it cleanly cloneable." That's the cheapest safe path to public. **Directive: extract personal config now; commit to self-host-per-user as the public model unless you truly want to run a service.**

---

## Weakness 4 — ~660 flat root files, hard to hand off

**The Architect (Gemini).** Public release means contributors and your own ability to maintain a release branch. Group into packages (`memory/`, `harness/`, `browser/`, `documents/`), move smokes to `tests/`. Strongly consider that the public version is a *separate, hardened codebase* — not the personal repo with your life wired into it.

**The Planner (GPT).** This is now on the critical path, not adjacent to it. Nobody — including future-you — can prepare a public release from a 660-file flat root. Start with the `tests/` move (zero logic change), then packages. Do it before the public-hardening work, because every other pre-public task lands in this structure.

**The Contrarian (Grok).** The bus factor is one, and you're about to invite the world to look. A flat, personal repo is fine for a solo tool and embarrassing-to-dangerous as a public project. This is the credibility item.

**Chairman verdict — severity 4 (was 4).** Same severity, now firmly gating. The key new guidance: **the public release should live in its own clean repo** (call it what you like), seeded from a restructured core — so your personal wiring never ships. **Directive: restructure into packages + `tests/`; stand up the public version as a separate hardened repo, not a fork carrying personal config.**

---

## Weakness 5 — Plaintext credentials, host execution

**The Architect (Gemini).** Public changes this from "protect my machine" to "protect strangers' machines and keys, and run untrusted input safely." Three layers: credentials at rest (→ OS keychain / encrypted store), tool sandboxing (containerize the high-blast-radius tools), and never letting input widen permission scope.

**The Planner (GPT).** Credentials → keychain now (cheap, helps you today). Sandboxing is the big pre-public project — stage it by blast radius: shell, repo writes, **browser**, file deletes first. This is the literal OpenClaw-nightmare prevention; it must be done before a single external user.

**The Contrarian (Grok).** For your own machine today, low urgency. The day you hand Maya to user #2, it's the highest-severity item on the board. Don't ship public without it — that's the line between "trustworthy agent" and "next OpenClaw headline."

**Chairman verdict — severity 5 (was 4, latent).** The defining gate between Maya's positioning and the category's worst outcome. **Directive: keychain now; sandboxing + injection-scoped permissions are non-negotiable pre-public.**

---

## Weakness 6 — macOS-only AppleScript browser control  →  now front-line (heavy use + cross-platform + attack surface)

**The Architect (Gemini).** This jumps the most. Heavy personal use means reliability matters *today*; public release means Windows/Linux users can't run AppleScript at all; and a heavily-used browser is the #1 prompt-injection vector. The driver is already abstracted (`make_browser_controller`), so a CDP/Playwright driver behind the same interface is contained — but it's now urgent on three axes at once.

**The Planner (GPT).** Re-rank this to near the top. (1) Migrate to CDP/Playwright for reliability + cross-platform. (2) Wrap the browser tool in the sandbox (it's the highest-risk surface). (3) Run all page content through the sensitive-info / injection filter before it can influence an action. These three overlap with Weakness 5's sandboxing — do them together.

**The Contrarian (Grok).** You browse a lot, so AppleScript fragility is costing you *now*, not someday. Even ignoring public release, this earns its place. Add public + injection risk and it's no longer a footnote — it's a headline feature that's also your biggest hole.

**Chairman verdict — severity 4 (was 2).** The largest re-rating in the review. It's simultaneously your most-used capability and your largest attack surface — fixing the driver (reliability/cross-platform) and hardening the surface (sandbox + injection filter) are the same project. **Directive: migrate to CDP/Playwright and treat the browser as untrusted-input surface #1; do it alongside sandboxing.**

---

## New Weakness 7 — Prompt injection at scale (emergent from heavy browser + public)

**The Architect (Gemini).** The permission kernel gates *actions* regardless of instruction origin — good. The gap is *exfiltration*: injected text that asks Maya to read sensitive data and send it through an allowed channel. Heavy browsing multiplies the injection entry points; public users multiply the targets.

**The Planner (GPT).** Treat every read-surface (browser, Omi, screen, documents) as untrusted. Injected instructions must never widen Maya's permission scope or trigger a send/upload without a human gate. This is a policy layer on top of the kernel you already have, not a rebuild.

**The Contrarian (Grok).** This is the one that actually bites public agents. Capability bugs annoy users; an injection that exfiltrates a user's data ends the project. Prioritize it with the browser work — they're the same surface.

**Chairman verdict — severity 5 (new).** The defining risk of a heavily-browsing public agent. **Directive: build an "untrusted input" boundary — page/transcript content can inform answers but can never widen scope or trigger external sends unprompted.**

---

## New Weakness 8 — Multi-tenant data isolation (emergent from public)

**The Architect (Gemini).** Distinct from Weakness 3's plumbing: this is the *guarantee* that one user's memories, artifacts, and audit rows are provably invisible to another. Your canary + audit machinery is the perfect tool to *prove* isolation — extend canaries to cross-tenant leak checks.

**The Planner (GPT).** If you choose self-host-per-user (Weakness 3), this largely dissolves — separate processes, separate databases, no shared surface. If you choose hosted-multi-tenant, this becomes a major, test-heavy workstream. The architecture choice in Weakness 3 decides the size of Weakness 8.

**The Contrarian (Grok).** Another reason to pick self-host-per-user: you get isolation for free instead of engineering (and being liable for) it.

**Chairman verdict — severity 5 if hosted, ~1 if self-hosted (new).** Almost entirely determined by the Weakness 3 decision. **Directive: let the self-host-per-user choice neutralize this; only take on cross-tenant isolation if you deliberately choose to run a service.**

---

## Chairman's Recompiled Verdict & Phased Roadmap

The two new facts collapse into one strategic conclusion: **commit to "self-host-per-user, cross-platform, sandboxed" as the public model, and most of the scary items shrink.** That single architectural choice neutralizes multi-tenant isolation (W8), shrinks multi-user wiring (W3) to "make it cloneable," and frames the browser and sandbox work cleanly. The browser is the through-line — it's your most-used feature, your cross-platform blocker, and your top injection surface, all at once.

### Recompiled severity (public-release lens)

| # | Weakness | Old sev | New sev | Why it moved |
| --- | --- | :---: | :---: | --- |
| 5 | Plaintext creds / no sandbox | 4* | **5** | Public = others' keys/machines; the OpenClaw gate |
| 3 | Single-user wiring | 3* | **5** | Hard blocker — but self-host-per-user shrinks it |
| 7 | Prompt injection at scale | — | **5** | Emergent from heavy browser + public |
| 8 | Multi-tenant isolation | — | **5 / 1** | 5 if hosted, ~1 if self-hosted |
| 1 | Thin agentic loop | 4 | **4** | Same, but verifier fix now safety-gating |
| 4 | Flat 660-file codebase | 4 | **4** | Now critical-path; public repo must be clean |
| 6 | AppleScript browser | 2 | **4** | Biggest jump — used heavily + cross-platform + attack surface |
| 2 | Lexical memory | 3 | **3** | Same; cheap win, bigger payoff at scale |

### Roadmap

**Phase 0 — Now, while personal (cheap wins, help regardless of timeline)**
Fix `verify_goal` to fail-closed. Flip memory rerank always-on + neighbor boost. Move credentials to the macOS Keychain. Start running browser/screen/Omi content through the injection filter. Extract personal constants into one config file. *None of these require deciding the public model; all of them make Maya better today.*

**The Gate — do not onboard a second human until ALL of these hold**
Tool execution is sandboxed (browser, shell, repo, deletes). Read-surfaces cannot widen permission scope or trigger external sends (W7 closed). Credentials are encrypted at rest. The public codebase is a separate, restructured repo with no personal wiring. The browser runs on CDP/Playwright cross-platform. A per-user instance is provably isolated (self-host-per-user).

**Phase 1 — Pre-public hardening**
Sandbox the tools. Migrate the browser to CDP/Playwright. Restructure into packages + `tests/` and seed the clean public repo. Build the untrusted-input boundary. Add BYO-key onboarding and an installer (pipx/Docker).

**Phase 2 — Public + differentiate**
Ship the governed LLM Council on `/complex`, the "remembers like a human, forgets like a contract" memory story, and the auditable-by-design safety narrative — the things the capable-but-dangerous crowd structurally can't offer.

**One Chairman note, unchanged from v1:** every directive preserves the governance shell. The reason Maya can credibly go public where OpenClaw became a cautionary tale is that her differentiator *is* the safety posture. Don't trade it for speed — productize it.
