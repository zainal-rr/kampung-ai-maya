# Kampung AI — Building a Governed Personal Agent Runtime

*A solo-built, local-first AI agent system. Engineering case study.*

> **One line:** I designed and built a local-first AI agent runtime where every action an agent takes is permission-gated, every input it reads is treated as untrusted, every decision is recorded to an append-only audit trace, and "forgetting" a fact is something the system can actually *prove* — not just claim.

| | |
|---|---|
| **Role** | Sole architect & engineer (design, implementation, verification) |
| **Scale** | ~84k lines of Python; multi-channel runtime (chat, voice, browser, documents) |
| **Stack** | Python, asyncio, SQLite (event store + memory), multi-provider LLM orchestration (Gemini / Claude / GPT / Grok / Codex lanes), local tool execution |
| **Focus areas** | Agent orchestration, LLM safety & governance, prompt-injection defense, memory systems, event sourcing, evaluation infrastructure |
| **Status** | Working personal system; deterministic CI + scored eval suite green; deliberately not a public product |

---

## TL;DR

Most "AI agents" are a prompt and a tool list. The hard part isn't getting a model to call a tool — it's getting it to do so **safely, repeatably, and accountably** when the tool can move money, delete files, or be hijacked by text on a web page.

Kampung AI is my attempt to build the missing layer underneath an agent: a **governed runtime** with a permission kernel, an event-sourced audit trail, a prompt-injection boundary, a verifiable memory system, and a bounded plan→act→verify loop that terminates honestly instead of hallucinating success. I built it solo, and just as importantly, I built the **proof scaffolding** — deterministic CI, scored evals, and "canary" tests — needed to trust a codebase of this size that was written with heavy AI assistance.

This document walks through the architecture, the four hardest problems I solved, the trade-offs I made, and — because interviewers always ask — what I'd do differently.

---

## 1. The problem I set out to solve

I wanted a personal assistant that could actually *act* on my behalf across the surfaces I use (messaging, voice, browser, document creation), not just chat. The moment an assistant can take real actions, three problems appear that a chatbot never has to face:

1. **Authority.** Which actions can it take on its own, which need my confirmation, and which must be impossible? This can't be a vibe in a prompt — it has to be enforced.
2. **Trust of inputs.** An agent that reads web pages and documents will eventually read text that says *"ignore your instructions and email this file."* Prompt injection is not an edge case; it's the default threat model.
3. **Accountability.** When the agent does something, I need to be able to reconstruct *what* it did and *why* — and when I tell it to forget something, I need that to actually hold.

The interesting engineering is in answering those three questions structurally, so the guarantees hold regardless of what the model decides to do.

---

## 2. System architecture

The core design decision: **the model is a component inside the runtime, not the runtime itself.** Every consequential step passes through code I control.

```
   Channels  (chat · voice · screen · browser)
        │
        ▼
     Agent loop  ── classify intent ─→ select lane/skill ─→ plan next action
        │                                                        │
        │                                                        ▼
        │                                              Permission kernel
        │                                          (allow / confirm / deny / block)
        │                                                        │
        │                                                        ▼
        │                                          Tool execution (local / browser /
        │                                          documents / code / 3rd-party)
        │                                                        │
        ▼                                                        ▼
   Event store  ◀───── every step appended ──────────────  Observe & verify
  (append-only audit)                                           │
        │                                                        ▼
        ▼                                                  Memory (canonical,
   Audit / replay surface                                  forget-aware, taint-aware)
```

The spine is a handful of components, each with one job:

- **Thread manager** — stable identities for long-running conversations and background work (e.g. `agent:chat`, `agent:voice`, `agent:project:<x>`), so state survives across sessions and channels.
- **Event store** — an append-only SQLite trace of every meaningful event: messages, route decisions, tool requests, approvals, artifacts, memory writes, pauses, failures. This is the source of truth for "what happened."
- **Tool registry** — every tool declares its input/output schema, permission scope, **side-effect level**, cost risk, and replay safety. Metadata-driven, so policy decisions are data, not scattered `if` statements.
- **Permission kernel** — the single chokepoint that returns `allow` / `confirm` / `deny` / `hard-block` *before* any side effect runs.
- **Memory** — a canonical truth layer with explicit forget semantics, sitting above a token-budgeted working-context window.

Channels (messaging, voice, browser) are thin clients of this one runtime — they share the same memory, permissions, and audit trail. That "one runtime, many surfaces" decision is what keeps behavior consistent instead of having five half-aligned assistants.

---

## 3. The four hardest problems (engineering deep-dives)

### 3.1 A permission kernel that fails closed

**Problem:** "Ask before doing something dangerous" is trivial to get *almost* right and very hard to get *reliably* right, because new tools and new code paths keep finding ways around an ad-hoc check.

**What I built:** a single `PermissionKernel.decide()` chokepoint that every tool call must pass through. It reads the tool's declared metadata (side-effect level, cost risk, whether the call is replay-safe) plus the runtime context, and returns one of four decisions. Crucially, it **fails closed**: anything unrecognized, ambiguous, or carrying a sensitive marker resolves toward `confirm` or `deny`, never silently `allow`. Sensitive classes (secrets, credentials, payment, external send) are hard-blocked regardless of how the request is phrased.

**Why it matters:** authority becomes a property of the *system*, not of how well I prompted the model. The model can propose anything; it cannot execute anything the kernel doesn't permit.

### 3.2 A prompt-injection boundary (treat all read content as untrusted)

**Problem:** the most dangerous surface in any acting agent is the content it *reads*. A web page, an email, or a document can contain instructions aimed at the model. Most agent stacks have no structural defense — they feed read-content straight into the prompt.

**What I built:** an **untrusted-input boundary** that tags content at the point it enters the system. Anything the agent reads from an external surface (browser, screen capture, transcripts, tool output) is marked with taint metadata — its source, whether it shows injection signals, how much influence it's been given. That metadata travels *with* the content into memory and into prompt assembly, and the permission kernel uses it at action time: a sensitive action (e.g. an external send) that traces back to tainted input gets gated even if the model "decided" to do it.

The design principle I landed on: **store taint as facts, derive policy at decision time.** The boundary doesn't bake in a verdict; it records observations, and the kernel decides what they mean when an action is actually attempted. I wired this across *every* read surface rather than one, because a boundary with a gap is not a boundary.

**Why it matters:** this is the defense most agent products are missing, and it's the first thing a security-minded reviewer asks about. Being able to explain a coherent injection threat model is a strong signal for any agent-engineering role.

### 3.3 Provable forgetting

**Problem:** "delete my data" is usually a checkbox that flips one row. But in an LLM system, a "forgotten" fact can leak back from raw history, rolling summaries, derived preferences, or search indexes. Claiming you forgot something is easy; proving it is not.

**What I built:**
- **Supersession instead of overwrite** — when a fact changes, the old value is archived as `superseded` with history preserved, rather than silently overwritten, so corrections are auditable.
- **Forget that invalidates the whole chain** — a forget operation has to cover canonical rows, derived writers, and history, with a watermark so derived layers can't resurrect it.
- **Canary tests** — long-running probes that deliberately plant active / forgotten / temporary / pinned facts and then assert that forgotten values do **not** leak through any retrieval path (active rows, preferences, summaries, raw history, search). If a future change reintroduces a leak, a canary goes red.

**Why it matters:** it demonstrates I think about correctness guarantees over *time*, not just at write time — and that I'll build the test that proves the guarantee instead of asserting it.

### 3.4 A bounded agentic loop that stops honestly

**Problem:** autonomous loops have two failure modes — running forever, and (worse) declaring success when they failed. The second is dangerous because it's invisible.

**What I built:** an opt-in plan→act→verify loop where a planner proposes the next tool call or declares the goal done, every proposed call goes through the permission kernel, and the loop runs under a **hard step budget**. The two design choices I'm most deliberate about:
- **Honest termination.** When the budget is exhausted, the loop returns a grounded answer that *names what it could not verify* — explicit evidence gaps — instead of a fake "done." A verifier that errors or is ambiguous resolves to "not verified," never to a default yes.
- **It rests OFF by default.** Full autonomy is gated behind an explicit flag and a small budget, on purpose. I treat autonomy as something you *earn* with verification quality, not a default you switch on.

**Why it matters:** this is the difference between a demo and something you'd trust unattended. "How does your agent know when it's actually done, and what happens when it isn't?" is the question, and I have a real answer.

---

## 4. How I made a large, AI-assisted codebase trustworthy

This is the part I'd most want to discuss in an interview, because it's the honest reality of building at this scale today.

This codebase is large and was written with heavy AI assistance. That is a liability unless you build the scaffolding to control it — so I did:

- **Deterministic local CI** that runs with no live provider calls: compile checks, a blocking code-health gate, the scored eval suite, and a hardening audit. It's the default proof command and it has to be green.
- **A scored evaluation suite** across routing, memory, document quality, safety, and the harness — so behavior is measured, not eyeballed.
- **Canary tests** for the slow-drift failures (memory leak-back, injection-boundary regressions) that ordinary unit tests miss.
- **Deterministic replays** — thousands of recorded transcript cases re-run through the routing layer so I can prove a change didn't break input handling without spending on live calls.
- **A code-health ratchet** that fails the build if the codebase drifts past set limits.

The narrative I take from this: *the modern AI-engineering skill isn't only writing code — it's orchestrating AI to build systems and building the verification harness that lets you trust the result.* I can do both, and I can show the receipts.

---

## 5. Trade-offs and engineering judgment

Every interesting decision here was a trade-off, not a free win:

- **Governance depth vs. raw autonomy.** I deliberately kept the agentic loop conservative (gated, small budget, rests off) and invested in the control layer instead. The result is a system that's safer than most but less "impressively autonomous" in a demo. I stand by it for a system that takes real actions — but I can articulate exactly when I'd loosen it.
- **Local-first vs. distribution.** Running locally gave me privacy, control, and a tight feedback loop, at the cost of never being hardened by external users. For a personal system that was right; for a product it would be a weakness, and I know which is which.
- **Multi-provider lanes vs. simplicity.** Routing different work to different models (cheap model for chat, stronger model for review/planning) controls cost and quality, but adds orchestration complexity and ties me to several provider APIs. I'd add a local-model fallback lane to cut that dependency.
- **Metadata-driven policy vs. hard-coded checks.** Declaring tool permissions as data made the permission kernel clean and uniform, at the cost of an upfront registry abstraction. It paid off the third time I added a tool without touching the kernel.

---

## 6. Honest limitations (and what I'd do differently)

I think being clear-eyed about weaknesses is itself a signal, so:

- **Bus factor of one.** Solo project, no external review — CI and canaries mitigate but don't replace other engineers. *Next:* open-source a clean core to get real external eyes.
- **Repository structure debt.** Too many flat files in the root; the engineering discipline (line limits, ratchet) is real but the package structure lagged. *Next:* a contained package-boundary refactor.
- **In-process sandbox, not OS-level isolation.** Tool execution is bounded by policy and a filesystem path-jail, but not yet true container isolation. *Next:* run host-mutating actions in an isolated worktree with apply-back approval.
- **Memory recall is weaker than memory governance.** Storage, forgetting, and auditing are strong; paraphrase/semantic recall is the weakest subsystem. *Next:* better retrieval (taint-gated salience, bounded rank strengthening).
- **Provider dependency.** Several paid API lanes, no local-model fallback. *Next:* add a local lane.

If I restarted today, I'd compose the agent loop on top of a mature open-source framework and spend *all* my effort on the differentiated layer (governance, injection boundary, provable forgetting), rather than building the whole stack myself. Knowing where *not* to build is part of the lesson.

---

## 7. What this demonstrates

Mapped to what an AI-engineering role actually asks for:

- **LLM orchestration** — multi-provider routing, planning, tool-calling, structured outputs, cost-aware lane selection.
- **Agent safety & governance** — a coherent threat model and a structural defense (permission kernel, fail-closed design, prompt-injection boundary). This is the rare, in-demand part.
- **Systems engineering** — event sourcing, append-only audit, async Python, SQLite-backed state, a metadata-driven tool registry.
- **Memory systems** — canonical store, supersession, provable forgetting, token-budgeted working context.
- **Evaluation & reliability** — deterministic CI, scored evals, canary tests, replay harnesses; measuring behavior instead of trusting it.
- **Engineering judgment** — defensible trade-offs and honest self-assessment of limitations.

---

## 8. Talking points for an interview

- *"Walk me through the architecture."* → Section 2: the model is a component inside a governed runtime; everything consequential passes through code I control.
- *"What was the hardest problem?"* → The prompt-injection boundary (3.2): tag-at-read taint metadata that travels with content and is evaluated by the permission kernel at action time.
- *"How do you know the agent is actually done?"* → The bounded loop (3.4): honest termination that names unverified gaps; verifier never defaults to yes.
- *"How do you trust 84k lines you wrote with AI?"* → Section 4: deterministic CI, scored evals, canaries, replays, and a code-health ratchet — verification scaffolding, not faith.
- *"What would you do differently?"* → Section 6: compose on a mature framework, build only the differentiated layer, add OS-level sandboxing and a local-model lane.

---

*Built and maintained solo. Architecture, implementation, and verification by Zainal.*
