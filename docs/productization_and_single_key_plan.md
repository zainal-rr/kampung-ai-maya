# Kampung AI: Productization, Single-Key, and Enterprise Segmentation Plan

This document answers three questions: where Kampung AI stands today and how far it
is from "fully agentic," how it compares to the June 2026 market, and how to take it
from a single-user personal harness to a public + enterprise product that can run on
one API key per deployment. It is a strategy/plan layer on top of `KAMPUNG_AI.md`,
`docs/public_architecture.md`, and `docs/proof_and_readiness.md`.

---

## 1. Where It Stands Today

Kampung AI is already a real agent runtime, not a chatbot wrapper. The hard part — the
spine — is built:

- A LangGraph harness (`harness_graph.py`) with a genuine agentic loop:
  `ingest → classify → plan → safety_check → execute → observe → verify → (loop|finish)`,
  checkpointed and resumable via `AsyncSqliteSaver`.
- A permission kernel (`maya_permission_kernel.py`) and tool registry
  (`maya_tool_registry.py`) that gate every side effect with allow/confirm/deny/hard-block,
  plus side-effect level, cost risk, and replay-safety metadata.
- A provider-agnostic planner seam (`harness_llm_planner.py`): `plan_with_llm`,
  `choose_next_action`, `verify_goal` all take an injected `llm_call(prompt) -> str`
  hook. **This is the single most important asset for everything below.**
- Event-sourced traces, canonical memory with forget-integrity, artifact quality gates
  (Word/Excel/PPTX), and channel delivery across Telegram, iMac voice, screen, browser.

By the project's own conservative scoring: overall ~84-86%, agentic workflow ~78-82%,
document creation ~90%, browser ~90-92%, hardware/maker ~65-70%.

### How far from "fully agentic"?

Architecturally, ~80% there. The distance is **reliability and autonomy depth, not a
rewrite**:

| Gap | Today | Fully agentic |
| --- | --- | --- |
| Autonomy default | `MAYA_AGENTIC_LOOP=0` (opt-in), 8-step budget | On by default, dynamic budget with cost ceilings |
| Planner quality | One-shot JSON plan + tool pick; YES/NO verifier | Reflection/self-critique, re-planning on failure, sub-goals |
| Tool surface in loop | browser/screen/doc/memory remaps only | Full registry callable, including code + external connectors |
| Multi-agent | Single planner; `/complex` fans out 2-4 Gemini subagents | Orchestrated specialist agents (Manus CodeAct style) if needed |
| Proof | Deterministic replays strong; no 30-day soak | 30-day soak + 50 live browser + 30 live voice tasks recorded |

The honest read: **the agentic foundation is more rigorous than most shipped "agents."
What's missing is proven, always-on reliability — not capability.** Turn the loop on,
deepen the planner, widen the tool surface, and run the soak.

---

## 2. Market Position (June 2026)

| Product | Strength | Weakness vs Maya | What to borrow |
| --- | --- | --- | --- |
| **Claude Cowork** (GA, enterprise) | Best for local file ops; shipped enterprise RBAC, group spend limits, usage analytics, OpenTelemetry, per-tool connector controls; Managed Agents + private MCP | Cloud/account-bound; not a personal multi-channel voice presence | The exact enterprise feature set you want is now table stakes — match it |
| **OpenAI Operator** | Browser computer-use agent, unified with Deep Research | $200/mo Pro; stops constantly for permission; web-only | Browser CUA depth; your permission gating is already smarter (graded, not constant) |
| **Manus Desktop** | CodeAct: multi-agent in isolated Linux sandbox, executes Python to call any library | Less privacy/local-first; heavier | Sandbox-Python-as-action pattern for the agentic loop |
| **Lindy / alfred_** | Autonomous, proactive email/workflow automation; persistent memory | Narrow (inbox/workflow); not multi-channel/voice | Proactivity — Maya is still mostly reactive |
| **Google Project Astra** | Real-time multimodal, screen + camera | Not local, not yours | Live multimodal fluidity |

**Maya's defensible differentiators:** local-first / air-gapped privacy, true multi-channel
(voice + Telegram + screen + browser as one runtime), Malay/Manglish, canonical memory with
*forget-integrity* (rare in market), and document quality gates that reject filler. **The
two things the market has and Maya doesn't yet:** (1) multi-user/cloud + billing, and (2)
proactive, always-on autonomy. Memory and "does it for you" are now baseline expectations.

---

## 3. The Single-Key Decision (OpenAI vs xAI)

### The reframing

Do **not** hard-collapse all five lanes (Gemini sight, Claude steward, GPT planner, Grok
voice, Codex hands) into one model permanently. That throws away the lane design that is
your moat. Instead make **"one API key" a per-deployment configuration behind a provider
abstraction layer.** The planner hook in `harness_llm_planner.py` already proves the seam
exists; extend that pattern to every lane (chat, vision, voice, review, code) so a lane is
"a capability + a default provider," not a hardcoded vendor.

That single change is what makes all three of your goals possible at once: public users on
one key, enterprises on their own key, and a private-Claude tenant — same codebase.

### The decisive technical fact

**xAI's Grok Voice Agent API is compatible with the OpenAI Realtime API spec** (and ships a
LiveKit plugin). So you don't actually have to choose permanently for voice: build the voice
client to the **OpenAI Realtime spec**, and OpenAI vs xAI becomes a base-URL + key swap.

### The numbers that matter for a public product

| | OpenAI (gpt-realtime-2) | xAI (Grok Voice Agent) |
| --- | --- | --- |
| Speech-to-speech voice | Yes, with tool use | Yes, with tool use, **OpenAI-spec compatible** |
| Voice cost | ~$0.25–0.35/min all-in (caching helps) | **$0.05/min flat** |
| Audio reasoning | Strong | **#1 on Big Bench Audio** |
| Multilingual (Malay/Manglish voice) | Good | Native multi-language, mid-conversation switching |
| Agentic text / function calling / ecosystem | Most mature (Agents SDK, LiveKit, broad tooling) | Newer, narrower ecosystem |
| Vision / document reasoning | Strong | Adequate |

### My recommendation

**Default the public consumer tier to OpenAI, but build the voice and planner clients to the
OpenAI Realtime / function-calling spec so xAI is a drop-in alternative.** Reasoning:

1. For a single-vendor key, OpenAI gives the most *complete* coverage in one account:
   realtime voice + STT/TTS + agentic text + function calling + vision. Maya's hardest work
   is agentic (planning, browser, documents), and OpenAI's tool-use stack is the most mature.
2. Because Grok is OpenAI-spec-compatible, you keep xAI's 5–7× cheaper voice and best-in-class
   audio as a **swappable option** with no rewrite. If voice minutes become the dominant cost
   at scale, flip the voice lane's base URL to xAI per tenant.
3. Re-test Malay/Manglish on Grok *voice* specifically — the doctrine flags Grok's *text*
   Malay quality, but voice is a different model and benchmarks well; it may now be good enough.

**Pick xAI as the single default instead if and only if** voice volume dominates your cost
model and the multilingual voice quality tests well — then you get one cheap key that still
speaks the OpenAI dialect, with OpenAI as your fallback. Either way the abstraction layer means
the choice is reversible, which is the real win.

---

## 4. Public + Enterprise Architecture ("Cisco ISE" mapping)

Your Cisco ISE instinct is the right mental model. ISE is identity → policy → segmentation →
posture → enforcement. Maya already has the enforcement layer; productizing is mostly adding
the layers above it and scoping them per tenant.

| Cisco ISE concept | Maya equivalent | Status |
| --- | --- | --- |
| Identity (who) | Tenant + user auth, SSO/OIDC | **To build** |
| Policy (what they get) | Per-tier model/provider, tool allowlist, spend cap | Partial — registry exists, not tenant-scoped |
| Segmentation (isolation) | Per-tenant memory DB, artifact store, thread namespace, key vault | Partial — namespaces exist (`maya:...`), not isolated per tenant |
| Posture (is the action safe) | Permission kernel safety checks before side effects | **Built** (`maya_permission_kernel.py`) |
| Enforcement | allow/confirm/deny/hard-block + approval gates | **Built** |

So the work is: wrap the existing single-user runtime in a **tenant context** that carries
`{tenant_id, tier, provider_key, model_policy, tool_policy, spend_budget, data_namespace}`,
and thread that context through the harness, registry, kernel, and memory so every decision is
tenant-scoped.

### Proposed tiers

| Tier | Deployment | Key model | Segmentation | Notes |
| --- | --- | --- | --- | --- |
| **Public / consumer** | Hosted cloud, multi-tenant | One shared platform key (OpenAI default), metered per user | Logical isolation: per-user memory namespace + row-level scoping | Billing + rate limits required; lightest |
| **Pro / prosumer** | Hosted, isolated workspace | Shared key or BYOK | Dedicated memory DB + artifact store per workspace | Group spend limits, usage analytics |
| **Enterprise** | Dedicated VPC / on-prem / "private Claude" | **BYOK** (their OpenAI/xAI/Azure/Bedrock, or Anthropic via Managed Agents + private MCP) | Hard isolation: separate DB, key vault, audit log, network boundary | RBAC, SSO, OpenTelemetry audit, per-tool connector controls — match Cowork's enterprise set |

"Use it in public **or** private Claude" falls out naturally: the public tier runs on your
hosted key; the enterprise tier can target a **private Claude** deployment (Claude Managed
Agents in a sandbox they control + private MCP servers) by configuring the steward/agentic lane
to Anthropic and pointing connectors at their MCP — same provider-abstraction seam.

---

## 5. Phased Roadmap

**Phase 0 — Provider abstraction (the unlock).** Generalize the `llm_call` pattern from the
planner to every lane. Define capability interfaces (`chat`, `vision`, `voice_realtime`,
`review`, `code`, `embedding`) each resolving to a provider+model from config. Ship a "single-key
mode" that points all capabilities at one provider. Build voice to the OpenAI Realtime spec.
*Outcome: the repo can run on one key without losing the lane design.*

**Phase 1 — Tenant context + policy.** Introduce a `TenantContext` threaded through harness,
registry, kernel, and memory. Make the permission kernel tenant-policy-aware (tool allowlist +
spend budget per tier). Namespace and isolate memory/artifacts per tenant.
*Outcome: the Cisco-ISE policy/segmentation layer.*

**Phase 2 — Public deployment.** Hosted runtime (containerized, the `launchd` appliance becomes
a service), auth (OIDC/SSO), metering + billing, per-user data isolation, rate limiting, abuse
controls. Default provider = OpenAI single key.
*Outcome: public users on one platform key.*

**Phase 3 — Enterprise / private-Claude tier.** BYOK + key vault, dedicated isolation, RBAC,
audit trails + OpenTelemetry, per-tool connector controls, optional private-MCP / Managed-Agents
target. Match the Cowork enterprise feature set as the baseline bar.
*Outcome: enterprise segmentation; private-Claude option.*

**Phase 4 — Close the agentic gap.** Turn the loop on by default with cost ceilings, deepen the
planner (reflection, re-planning, sub-goals), widen the in-loop tool surface, and run the 30-day
soak + 50 live browser + 30 live voice tasks the proof doc requires.
*Outcome: "fully agentic" by reliability, not just architecture.*

Phases 0–1 are prerequisites for everything; 2 and 3 can proceed in parallel after 1; 4 should
run continuously alongside.

---

## 6. Risks To Watch

- **Capability regression from single-key.** A weaker single model may underperform the current
  best-of-breed lanes (Claude review, Gemini sight). Mitigation: the abstraction layer lets
  enterprise tenants opt back into multi-provider; benchmark each lane before defaulting it.
- **Voice cost at scale.** Voice minutes are the dominant variable cost. Mitigation: xAI swap +
  prompt caching + idle session closing (the doctrine's "never open all day" rule already helps).
- **Privacy promise vs cloud.** Maya's identity is local-first/air-gapped; a public cloud tier
  dilutes that. Mitigation: keep local-first as the consumer privacy story; sell isolation
  (dedicated VPC/on-prem) as the enterprise story.
- **Memory isolation bugs = cross-tenant leakage.** The forget-integrity work must extend to
  tenant boundaries. Mitigation: tenant-scoped canaries in the existing memory canary harness.
- **Multilingual quality on a single vendor.** Re-validate Malay/Manglish before committing.
