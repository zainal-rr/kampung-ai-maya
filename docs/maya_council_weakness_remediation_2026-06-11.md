# Maya / Kampung AI — Council Weakness Remediation (Session Handoff)

Date: 2026-06-11
Author: Claude (Cowork session)
Source review: `MAYA_PUBLIC_RELEASE_COUNCIL_REVIEW.md` (8 weaknesses, public-release lens)
Method: Karpathy "LLM Council" — applied as a review discipline both before coding (scope triage) and after testing (code review).
Purpose: shareable status + spec doc for the next session to continue from.

---

## 2026-06-11 implementation addendum

This handoff originally described W7 as kernel-complete but entry-dormant. That
is no longer the current code state.

- **W7 live-wired:** browser page text, Chrome extension page text,
  screen/vision summaries, active-context extraction, harness observations,
  LangGraph permission checks, and SDK tool calls now carry
  `untrusted_influence` / `injection_detected` into the permission kernel.
  Guard smokes: `untrusted_input_boundary_smoke.py` and
  `untrusted_live_path_smoke.py`.
- **W3 config extraction:** `maya_runtime_config.py` centralizes the main
  personal/runtime constants: owner name, Telegram allowlist, workspace roots,
  project roots, audio device preferences, browser driver default, and voice
  defaults. Existing `.env` names remain supported. Guard smoke:
  `runtime_config_smoke.py`.
- **W5 secret provider:** `secret_provider.py` adds `env`, `keychain`, and
  `auto` modes. Default remains `env`; migration to Keychain is explicit. A
  throwaway macOS Keychain write/read/delete check passed on this iMac. Guard
  smoke: `secret_provider_smoke.py`.
- **W6 browser driver:** Chrome extension is now strict normal mode; AppleScript
  requires `MAYA_BROWSER_DRIVER=legacy`. Guard smoke:
  `browser_driver_mode_smoke.py`.
- **W2 decision:** baseline and embedding-rerank memory evals produced identical
  recall, so embedding rerank remains env-gated/off by default.

The old W7 integration spec below is preserved as historical context, but the
work it asks for has been implemented. Future sessions should add new entry
surfaces to the same boundary rather than rebuilding it.

---

## 0. Honest note on the council architecture

A true LLM Council needs four *different vendor* models answering independently
(Gemini / GPT / Grok / Claude), then a chairman synthesizes. This session is a
single model, so what ran here is the council *method* — independent
role-based perspectives then synthesis — not four separate vendors. It is
genuinely useful for catching blind spots, but it is not a four-vendor council.

The real four-vendor council is buildable, and Maya already has the lanes for
it (`ModelLanes`: Gemini sight, GPT mind, Grok/xAI, Claude steward). Shipping a
governed council on `/complex` is literally **Phase 2** of this very review's
roadmap. Recommendation: build it there — it is the differentiator the review
names, and it would let Maya run real multi-vendor deliberation on hard
questions instead of relying on a single lane.

---

## 1. What was BUILT and TESTED in this session

Two of the eight are pure-logic, in-lane, and deterministically testable in a
sandbox without live keys or platform APIs. Both done with smokes.

### W1 — Fail-closed agentic verifier (severity 4, safety-gating) — DONE, LIVE

**Defect:** `harness_llm_planner.verify_goal` returned `True` on BOTH provider
error AND ambiguous model output — a broken verifier silently declared the
goal "satisfied". Once untrusted users can invoke the loop, that is a safety
defect, not just a correctness one (council W1 directive: fail-closed first).

**Fix:** only an explicit `YES` satisfies the goal. On ambiguity, one
reflective retry with a tighter instruction; on error, log and retry; then
return `False`. `False` keeps the loop open — which is safe **because
`MAX_STEPS` bounds it**. Fail-closed verifier + hard budget = never-falsely-done
AND never-infinite.

**Status:** live-effective (it is on the agentic loop path). Default behavior
unchanged for explicit YES/NO. `harness_agentic_deep_smoke` still green.

**Tradeoff (documented, accepted per council):** a genuinely-done run whose
verifier errors will now loop to the step budget instead of stopping early.
Bounded by `MAX_STEPS=8`; agentic loop is opt-in (`MAYA_AGENTIC_LOOP=0`
default). Safety > wasted steps, per the directive.

### W7 — Untrusted-input boundary (severity 5, new) — KERNEL-WIRED + REGISTRY-DRIVEN (2026-06-11 update)

**UPDATE 2026-06-11:** the registry-vocabulary bug is fixed and the boundary is
now wired into `MayaPermissionKernel.check`. External/scope-widening reach is
resolved from `MayaToolSpec.side_effect_level` (`external`/`repo_write`), with
the action-name sets as fallback, and **unknown actions fail closed** (treated
as external). The kernel applies it after the base decision via optional
`untrusted_influence` / `injection_detected` params — default off, so existing
behavior is byte-identical. End-to-end smoke proves an injected page +
`telegram.send_file` is DENIED. **Remaining: tag untrusted content at entry**
(browser/screen/omi/document adapters set the two flags on turn state) — owned
by the browser session; spec unchanged below. Original module description:

**Threat:** exfiltration-via-injection. The permission kernel gates actions by
type regardless of who asked — good. The gap is injected text in content Maya
*reads* (web page, Omi transcript, screen, document) that tries to make her
read sensitive data and send it through an allowed channel, or widen her
permission scope. Heavy browser use multiplies entry points; public users
multiply targets.

**Built:** `untrusted_input_boundary.py` — a policy layer on top of the kernel
(not a rebuild), pure logic, fully unit-tested:
- `assess_untrusted_content(text, source)` — flags injection signals
  (instruction-override, exfiltration, scope-widening) in content from
  untrusted sources (browser/screen/omi/document/web/email/pdf). User/iMac
  input is trusted and never flagged.
- `untrusted_action_decision(action_type, untrusted_influence, injection_detected, base_decision)`
  — applied AFTER the kernel; it can only TIGHTEN, never loosen:
  - injection + external-reach/scope-widening action → **DENY**
  - untrusted (even clean) influence + external-reach/scope-widening → **forced CONFIRM** (human gate)
  - local/non-external actions → unchanged
  - a kernel `deny` always stays `deny`

**Honest limitation (Contrarian, important):** the regex injection detection is
**bypassable** — a determined attacker phrases around it. The *robust* half is
the second rule: ANY external-send action under untrusted influence forces a
human gate, regardless of whether a specific injection string matched. The
regex is the bonus; the influence-gate is the real protection. Do not market
W7 as "injection-proof."

**Status:** module + smoke complete (`untrusted_input_boundary_smoke.py`).
NOT yet wired into the live action path (the kernel hot-path is being edited by
the concurrent session; blind-wiring risks collision). Integration is a precise
2-point spec below.

#### W7 integration spec (for the owning session)

1. **Tag untrusted content at entry.** Where browser page text, screen OCR,
   Omi transcripts, and document extraction enter the turn context, run:
   ```python
   from untrusted_input_boundary import assess_untrusted_content
   a = assess_untrusted_content(page_text, source="browser")
   turn_state["untrusted_influence"] = turn_state.get("untrusted_influence") or a.is_untrusted
   turn_state["injection_detected"] = turn_state.get("injection_detected") or a.injection_detected
   ```
2. **Tighten at the action gate.** In `maya_permission_kernel.MayaPermissionKernel.check`
   (or the SDK `call_tool` path), AFTER the existing decision:
   ```python
   from untrusted_input_boundary import untrusted_action_decision, boundary_notice
   boundary = untrusted_action_decision(
       action_type,
       untrusted_influence=turn_state.get("untrusted_influence", False),
       injection_detected=turn_state.get("injection_detected", False),
       base_decision=decision.decision,
   )
   # use boundary.decision; if boundary.forced_gate, surface boundary_notice(boundary)
   ```
   Add a smoke asserting an injected page + a `telegram_send` is denied end to end.

---

## 1b. Decisions made (2026-06-11)

**Public model = self-host-per-user (single-tenant).** Maya stays one-person
per instance; if Maya ever goes public, each user runs their own copy. This
decision is now fixed and it re-scopes two severity-5 items:

- **W8 (multi-tenant isolation): severity 5 → ~1.** Separate processes →
  separate databases → cross-tenant leakage is structurally impossible. No
  multi-tenant isolation engineering needed. (Only revisit if you ever
  deliberately choose to run a hosted service — you have chosen not to.)
- **W3 (single-user wiring): severity 5 → shrinks to "make cloneable".** No
  per-user isolation layer required. The only remaining work is extracting
  personal constants (chat IDs, device names, workspace paths, voice names)
  into ONE config module so a second person can clone Maya without editing
  source. That extraction is a Phase-0 cheap win, specced in §4.

**W6 driver direction = Chrome extension bridge (already in progress, other
session), NOT Playwright/CDP.** A Chrome extension is cross-platform by nature,
so this path addresses the council's cross-platform concern if the AppleScript
fallback is eventually dropped. The remaining W6 work is not the driver — it is
(a) putting the browser inside the sandbox (W5) and (b) running page content
through the W7 untrusted-input boundary before it can drive an action. W6 and
W7 are the same surface.

## 2. The remaining six — council verdict, ownership, next step

These were triaged OUT of this session: cross-session ownership (memory,
browser), untestable platform APIs (keychain, Playwright/Chrome), or
architecture decisions that are yours to make, not code to write.

| # | Weakness | Severity | Why not done here | Next concrete step |
| --- | --- | :---: | --- | --- |
| **5** | Plaintext creds / no sandbox | **5** | Keychain untestable in Linux sandbox; sandboxing is a large pre-public project | (a) creds → macOS Keychain now (cheap, helps today); (b) stage tool sandboxing by blast radius: shell → repo writes → **browser** → file deletes |
| **3** | Single-user wiring | **5 → ~2** | DECISION MADE: self-host-per-user. Now just "make cloneable" | Extract personal constants (chat IDs, device names, workspace paths, voice names) into ONE config module. Mechanical but touches many files — do it in a quiet window (no other session editing) to avoid collisions |
| **6** | AppleScript browser | **4** | In progress by concurrent session via Chrome **extension bridge** (not CDP/Playwright); needs live Chrome | Driver direction already chosen (extension). Remaining W6 = (a) browser inside sandbox (W5), (b) page content through W7 boundary. Same surface as W7 |
| **2** | Lexical memory, embeddings off | **3** | Owned by the concurrent memory session (FTS5/rerank work is theirs) | Flip always-on embedding rerank + 1-hop neighbor boost. Cheapest value-per-effort; multilingual payoff for SEA audience |
| **4** | 660 flat-file root | **4** | Large mechanical restructure; collides with everything in flight | Start with `tests/` move (zero logic change), then packages (`memory/ harness/ browser/ documents/`). **Public release = separate hardened repo**, seeded from restructured core, no personal wiring |
| **8** | Multi-tenant isolation | **5 → 1** | DECISION MADE: self-host-per-user dissolves this | No work needed. Separate processes/DBs = isolation for free. Only revisit if you ever choose to run a hosted service |

---

## 3. The Gate (council, verbatim intent)

**Do not onboard a second human until ALL of these hold:**
- Tool execution is sandboxed (browser, shell, repo, deletes).
- Read-surfaces cannot widen permission scope or trigger external sends unprompted (**W7 LIVE-wired**, not just module-complete).
- Credentials are encrypted at rest (Keychain / encrypted store).
- The public codebase is a separate, restructured repo with no personal wiring.
- The browser runs cross-platform (Chrome extension bridge — already in progress).
- ~~A per-user instance is provably isolated~~ — **SATISFIED by decision:
  self-host-per-user means separate processes/DBs; isolation is structural.**

W1 is done and live. W7 is now wired for the current browser/screen/document/
active-context/harness paths; future read surfaces must be added to that same
boundary before they are trusted.
The isolation gate item is satisfied by the single-user decision. The rest
(sandbox, encrypted creds, separate public repo, browser cross-platform) remain
open.

---

## 4. Recommended sequence for the next session

1. **Wire W7 live** (the 2-point spec above) + end-to-end injection smoke. This
   finishes the highest-new-severity item and closes one gate condition.
2. **Extract personal config** (W3 "make cloneable") — one config module for
   chat IDs, device names, workspace paths, voice names. Helps today, required
   for any public path, and forces the self-host-vs-hosted decision into the open.
3. **Creds → Keychain** (W5 cheap half) on the iMac, where it can be tested.
4. **Flip memory rerank always-on** (W2) — coordinate with the memory session.
5. Then the big pre-public projects (sandbox, Playwright, restructure) once the
   self-host-per-user decision is made — that decision shrinks W3 and W8.

Do NOT start the big items before the W3 architecture decision: it changes the
size of W8 from a major workstream to nearly nothing.

---

## 5. Files in this change

| File | Status |
| --- | --- |
| `harness_llm_planner.py` | W1: `verify_goal` fail-closed + reflective retry |
| `untrusted_input_boundary.py` | NEW — W7 policy module |
| `untrusted_input_boundary_smoke.py` | NEW — W7 + W1 deterministic smoke |
| `docs/maya_council_weakness_remediation_2026-06-11.md` | this handoff |

Smokes green: `untrusted_input_boundary_smoke`, `harness_agentic_deep_smoke`,
`maya_permission_kernel_smoke`, `permission_policy_smoke`, `secret_detection_smoke`,
`harness_graph_smoke`. No env or DB changes.

---

## 6. One strategic line (Chairman, unchanged from the review)

Every fix preserves the governance shell. Maya can credibly go public where
OpenClaw became a cautionary tale *because* her differentiator is the safety
posture — auditable memory, permission kernel, fail-closed verifier, untrusted-
input boundary, provable forgetting. Don't trade that for speed. Productize it.
The single decision that unlocks the cheapest safe public path is
**self-host-per-user** — it neutralizes W8, shrinks W3, and frames the browser
and sandbox work cleanly. Make that call before the big build.
