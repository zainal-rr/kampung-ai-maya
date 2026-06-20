# Open-Source Extraction Plan — "Keel" Governance Core

*Turning the governance layer of an 84k-line private runtime into a small, clean, reviewable open-source library.*

**Goal:** publish a framework-agnostic Python library that any agent builder can drop in to get (1) a fail-closed permission kernel on every tool call, (2) a prompt-injection taint boundary, and (3) an append-only audit trail. Small enough that a senior engineer can read the whole thing in an afternoon and trust it.

Working name throughout: **Keel** (placeholder — swap freely).

---

## The headline finding: the core is already decoupled

I traced the import graph of the governance modules before planning anything, and the result is the best case possible. The permission-kernel cluster has **zero imports from any Maya/Kampung-specific code** — no Telegram, no providers, no voice, no channels. It only imports from its own siblings and the Python stdlib.

```
maya_permission_kernel.py  (124 LOC)
   ├── maya_tool_registry.py     (192 LOC) ──┐
   │      └── permission_policy.py (198 LOC) │  permission_policy has
   ├── permission_policy.py  (shared) ───────┘  ONE dependency: pathlib
   ├── tool_sandbox_policy.py     (106 LOC)      (stdlib only)
   └── untrusted_input_boundary.py (282 LOC)     (stdlib only)
```

Five files, **~900 lines**, a clean internal tree, no external coupling. That means extraction is mostly *mechanical* (rename, repackage, design a public API, add tests and docs) rather than a risky untangling. The hard architectural work — keeping the governance layer free of application concerns — was already done. That's exactly the property that makes a clean OSS release feasible, and it's a strong thing to be able to say out loud.

The real effort is not decoupling. It's **genericizing content** (removing hardcoded Maya-specific tool names and strings), **designing a public API**, and **writing the tests and docs that make it trustworthy**.

---

## What to extract — three tiers

### Tier 1 — Governance core (the v0.1 release)

The cluster above. Ships first because it's clean, self-contained, and it *is* the differentiator.

| Module | LOC | Role | Coupling |
|---|---|---|---|
| `permission_policy.py` | 198 | Action → risk classification, hard-block rules | Leaf (pathlib only) |
| `tool_sandbox_policy.py` | 106 | Sandbox/blast-radius decisions, `stricter_decision` | Leaf (stdlib only) |
| `untrusted_input_boundary.py` | 282 | Taint metadata + `untrusted_action_decision` | Leaf (stdlib only) |
| `tool_registry.py` (was `maya_tool_registry`) | 192 | Tool metadata: schema, side-effect level, cost, replay-safety | → permission_policy |
| `permission_kernel.py` (was `maya_permission_kernel`) | 124 | The `allow/confirm/deny/hard-block` chokepoint | → the four above |

**This is the whole product at v0.1.** ~900 reviewable lines.

### Tier 2 — Audit trail (v0.2)

The append-only event store, so adopters get provable "what happened" out of the box.

| Module | LOC | Role | Coupling |
|---|---|---|---|
| `event_store.py` (was `maya_event_store`) | 127 | Typed append-only event API | → store backend |
| `store.py` (was `harness_store`) | 264 | SQLite-backed append-only persistence | stdlib (uuid, sqlite3) |

Clean (~390 LOC). The only work is making the SQLite path configurable and the event-type set extensible.

### Tier 3 — Provable forgetting (v0.3, harder)

The memory + canary system. This is the most *impressive* capability but the most *coupled* module — `canonical_memory.py` pulls in ~8 internal modules (embeddings, FTS, scoring, supersede, audit, links). Don't ship it in v0.1.

Strategy: extract only the **supersession + forget-watermark + canary** logic as a storage-agnostic mixin, leaving embeddings/FTS/scoring behind (they're recall-quality features, not the forgetting guarantee). The publishable artifact here is the **canary test suite** that proves forgotten data doesn't leak — that's the part nobody else has.

---

## What to leave behind (explicitly out of scope)

Everything that makes it "Maya" rather than "a governance library":

- Persona, Telegram, voice/STT/TTS, screen capture
- Office/document artifact builders, Blender/Maker workflows
- Model lanes / provider clients (Gemini, Claude, GPT, Grok, Codex)
- Browser drivers and channel delivery
- Scheduling, weekly memory automation, the Desk UI

The library must depend on **none** of these. If the core ever needs to import a provider or a channel, the abstraction is wrong.

---

## Target repository structure

```
keel/
├── README.md                  # what/why, 30-second quickstart, the threat model
├── LICENSE                    # Apache-2.0 (permissive → adoption)
├── pyproject.toml             # zero runtime deps beyond stdlib for the core
├── docs/
│   ├── threat-model.md        # the prompt-injection reasoning (link the blog post)
│   ├── permission-model.md    # allow/confirm/deny/hard-block semantics
│   └── audit.md
├── src/keel/
│   ├── kernel.py              # PermissionKernel — the public entry point
│   ├── registry.py            # ToolRegistry, ToolSpec
│   ├── policy.py              # risk classification + hard-block rules
│   ├── sandbox.py             # blast-radius / sandbox decisions
│   ├── taint.py               # UntrustedContext + action decision
│   ├── audit/                 # event store (v0.2)
│   └── adapters/              # langgraph.py, mcp.py, callable.py
├── examples/
│   ├── block_injection.py     # the money demo (see below)
│   └── basic_gating.py
└── tests/
    ├── test_kernel.py
    ├── test_taint.py
    └── canaries/              # the differentiator: leak-back + injection canaries
```

---

## Public API (keep it tiny)

The whole point is a surface a reviewer trusts at a glance:

```python
from keel import PermissionKernel, ToolRegistry, ToolSpec, UntrustedContext

registry = ToolRegistry()
registry.register(ToolSpec(
    name="send_email",
    side_effect="external_send",   # drives policy
    cost_risk="low",
    replay_safe=False,
))

kernel = PermissionKernel(registry)

decision = kernel.decide(
    action="send_email",
    args={"to": "...", "body": "..."},
    context=UntrustedContext(source="browser", injection_signals=True),
)
# decision.verdict in {"allow", "confirm", "deny", "hard_block"}
# → here: external_send + tainted browser context ⇒ "confirm" (escalated)
```

One object to construct, one method to call, a typed decision back. Everything else is internal.

---

## Adapters (framework-agnostic is the moat)

The core knows nothing about any agent framework. Thin adapters bridge it:

- **`adapters/callable.py`** — wrap any `tool(**args)` function so the kernel runs before it. The universal escape hatch.
- **`adapters/langgraph.py`** — a node/middleware that gates tool execution in a LangGraph graph.
- **`adapters/mcp.py`** — sit in front of MCP tool calls, gating + tainting + auditing them.

Ship `callable.py` in v0.1 (trivial, universal). Add LangGraph and MCP in v0.2 once there's interest.

---

## Tests & the canary proof (do not skip)

The tests *are* the marketing for a security library. Three layers:

1. **Unit** — every policy branch, every verdict, hard-block coverage.
2. **Property/fuzz** — random tool+context combinations never produce a silent `allow` for a sensitive sink driven by tainted input.
3. **Canaries** — the headline. A suite that plants hostile content and asserts it cannot reach a side-effecting sink unsupervised; and (for v0.3) that forgotten facts don't leak through any retrieval path. These are lifted almost directly from the private repo's existing canary suites — they already exist and pass.

---

## The "money demo" (`examples/block_injection.py`)

One runnable file that tells the whole story in <40 lines: a fake agent reads a web page containing an injection ("email these files to attacker@…"), tries to call `send_email`, and the kernel **blocks it** — with the audit trail printed showing *why*. This is what goes in the README gif and the blog post. If a visitor runs one thing, it's this.

---

## Phased roadmap (rough effort, solo)

| Phase | Scope | Est. effort |
|---|---|---|
| **0. Spike** | New repo, copy Tier-1 files, get them importing under `keel/`, delete dead branches | 1–2 days |
| **1. Genericize** | Strip Maya-specific tool names/strings; make hard-block list configurable; design the public API | 3–5 days |
| **2. Test + demo** | Port unit tests + injection canary; write `block_injection.py`; CI on GitHub Actions | 3–4 days |
| **3. Docs + release** | README, threat-model doc (reuse the blog post), LICENSE, `pip install` packaging → tag v0.1 | 2–3 days |
| **4. Audit trail** | Tier 2 event store + LangGraph/MCP adapters → v0.2 | 1 week |
| **5. Forgetting** | Tier 3 supersession + forget canaries → v0.3 | 1–2 weeks |

**v0.1 is realistically ~2 focused weeks.** That's the milestone that matters — it's the thing you link from your resume.

---

## Definition of done for v0.1 (what makes it credible)

- [ ] `pip install keel` works; core has zero non-stdlib runtime deps.
- [ ] `python examples/block_injection.py` blocks the attack and prints the audit reason.
- [ ] Green CI badge; tests + injection canary passing in GitHub Actions.
- [ ] README a stranger understands in 60 seconds, with the threat model up front.
- [ ] Apache-2.0 license.
- [ ] Public — linked from your LinkedIn, resume, and the blog post.

---

## Risks & honest caveats

- **"Feature, not a library."** A permission check can look thin. Mitigation: lead with the *taint boundary*, which is the non-obvious part, and the canaries, which prove it.
- **Genericization reveals coupling.** The import graph is clean, but there may be Maya-specific *strings/values* baked into `permission_policy.py`'s hard-block list. Budget Phase 1 for it; it's content work, not architecture work.
- **Maintenance burden.** An OSS repo invites issues. For a portfolio piece, "responsive solo maintainer with green CI" is fine; you don't need a community to get the hiring benefit — you need it to be real, readable, and yours.
- **Don't over-build before release.** v0.1 with one adapter and one demo beats a half-finished v0.3. Ship the small thing.

---

*The strongest version of your story isn't "I built an 84k-line system." It's "here are 900 lines of agent-security code you can read right now, with tests that prove the guarantee." This plan gets you there in about two weeks.*
