# Maya / Kampung AI — Remediation Priority Plan (Post-W1/W7 Council)

Date: 2026-06-11
Inputs: `MAYA_PUBLIC_RELEASE_COUNCIL_REVIEW.md` (8 weaknesses) + the W1/W7 handoff
(`docs/maya_council_weakness_remediation_2026-06-11.md`) + an independent code
review of what was actually built.
Method: Karpathy LLM Council — four role-seats deliberate independently, the
Chairman synthesizes a prioritized sequence.
Public model: **self-host-per-user** (decided 2026-06-11).

> Use this file in another session as the authoritative "what to do next" plan.
> It supersedes the priority tables in earlier reviews because two items moved:
> **W1 is done & live**, and **W7 is built but inert with a known wiring defect.**

---

## 0. Verified state going in (independently checked, not taken on trust)

- **W1 — fail-closed verifier: DONE & LIVE.** `harness_llm_planner.verify_goal`
  now only returns True on explicit YES; error/ambiguity → one reflective retry
  → False. Confirmed in source; `harness_agentic_deep_smoke` green. **Closed.**
- **W7 — untrusted-input boundary: BUILT, UNIT-TESTED, NOT WIRED.**
  `untrusted_input_boundary.py` + smoke present and passing. But it protects
  **nothing** until integrated into the action path — and the integration as
  currently specced has a defect (see W7-bug below). **Not closed.**
- **Decision — self-host-per-user:** collapses W8 (→1) and shrinks W3
  (→"make cloneable"). Each user runs their own instance; separate process =
  separate DB = isolation for free.

### W7-bug (must fix before/when wiring — found in code review)

The boundary decides "is this external?" with `action in EXTERNAL_REACH_ACTIONS`,
a hardcoded set (`telegram_send`, `share_file`, …). Maya's real tool registry
names those tools `telegram.send_file` and `mcp.call` — **not in the set.** So
wired as specced, the registry's two genuinely external tools evaluate
`external=False` → boundary returns base decision → **no gate.** Unknown action
types also default to non-external = **fail-open** (the same bug class W1 just
fixed). **Fix:** drive "external" off the registry's existing
`MayaToolSpec.side_effect_level ∈ {external, repo_write}` (and treat unknown
actions as external = fail-closed), instead of a divergent hardcoded list.

---

## 1. Council deliberation — what to tackle first

**Question put to the council:** given W1 closed and W7 built-but-inert, what is
the correct order for the remaining work, for a heavy-browser, self-host-per-user,
future-public Maya?

**The Architect (systems).** The browser is the spine of risk now: it's the
most-used surface, the top injection vector, and the thing public users run on
their own machines. W7 exists precisely to defend it but is currently inert.
Wiring W7 (correctly, registry-driven) is the highest-leverage single move —
it activates a severity-5 defense that's already 90% built. Everything else is
either cheap-and-independent (config extraction, keychain) or large-and-later
(sandbox, restructure).

**The Planner (sequencing).** Order by (leverage ÷ effort) and by unblocking:
finish what's nearly done before starting what's large. (1) Fix the W7 bug +
wire it live — small, finishes a started severity-5. (2) Extract personal config
— cheap, helps today, prerequisite for the public repo. (3) Keychain — cheap,
testable on the iMac. (4) Memory rerank — cheap, coordinate with the memory
session. THEN the big rocks: (5) sandbox, (6) browser-extension finish,
(7) restructure. Don't start a big rock while a started item (W7) sits inert.

**The Contrarian (blunt).** One inert security module is worse than none —
it invites false confidence. Until W7 is wired AND the vocabulary bug is fixed,
treat Maya as having NO injection defense and don't browse sensitive sites
under autonomy. Also: don't let "public someday" pull you into sandbox/restructure
now. You're personal today. Do the cheap things that also help you today; defer
the big public-only projects until just before launch.

**The Chairman (verdict).** Consensus is clean. The sequence is leverage-first:
**finish W7 (with the registry fix) before anything else**, because it converts
a built-but-useless severity-5 into a live defense and it's small. Then the
three cheap wins that help the personal product today (config, keychain,
memory). Then, and only when a public date is real, the big rocks. The single
gate that still blocks a second human is unchanged: sandbox + W7-live +
encrypted creds + clean public repo. W1 and the isolation item are already
satisfied.

---

## 2. Step-by-step order (do them in this sequence)

### STEP 1 — Wire W7 live, registry-driven (severity 5) — **DO FIRST**
- Fix the vocabulary bug: resolve "external/scope-widening" from the tool
  registry's `side_effect_level ∈ {external, repo_write}`; treat **unknown
  action types as external** (fail-closed).
- Tag untrusted content at entry (browser/screen/omi/document) → set
  `untrusted_influence` / `injection_detected` on turn state.
- Apply `untrusted_action_decision` AFTER the kernel decision in the
  `call_tool` path; surface `boundary_notice` on a forced gate.
- Add an end-to-end smoke: injected page + `telegram.send_file` → denied.
- **Why first:** smallest remaining severity-5; finishes a started item; turns
  an inert module into real protection for your most-used surface.
- **Owner:** the session that owns the kernel/browser hot-path (coordinate).

### STEP 2 — Extract personal config (W3 "make cloneable", severity →2)
- One config module for chat IDs, device names, workspace paths, voice names.
- **Why second:** cheap, helps today, hard prerequisite for any public repo,
  and forces no further decisions (self-host-per-user already chosen).
- **Caution:** touches many files — do it in a quiet window so it doesn't
  collide with the active memory/browser sessions.

### STEP 3 — Credentials → macOS Keychain (W5 cheap half, severity 5)
- Move provider keys out of `.env` into the Keychain / encrypted store.
- **Why third:** cheap, testable on the iMac today, directly closes the
  OpenClaw-class "infostealer lifts a working clone" risk. Independent of
  everything else.

### STEP 4 — Memory rerank always-on + 1-hop neighbor boost (W2, severity 3)
- Flip embedding rerank on by default; add the neighbor boost into
  `search_relevant_canonical_memories`.
- **Why fourth:** best value-per-effort capability gain; multilingual payoff;
  the nightly-consolidation links are already built. Coordinate with the
  memory session (their files).

### STEP 5 — Tool sandboxing (W5 hard half, severity 5) — **big rock, pre-public only**
- Containerize high-blast-radius tools, in this order: shell → repo writes →
  **browser** → file deletes.
- **Why here:** large project, only required before a second human. The browser
  belongs inside this sandbox (this is the other half of W6).

### STEP 6 — Finish browser extension bridge / drop AppleScript (W6, severity 4) — **owned elsewhere**
- Concurrent session is already migrating to a Chrome extension bridge
  (cross-platform by nature). Finish it and drop the AppleScript fallback.
- The remaining W6 risk is the *surface*, handled by STEP 1 (W7) + STEP 5
  (sandbox), not the driver.

### STEP 7 — Codebase restructure + separate public repo (W4, severity 4) — **pre-public only**
- `tests/` move first (zero logic change), then packages
  (`memory/ harness/ browser/ documents/`).
- Public release = a **separate hardened repo** seeded from the restructured
  core, with NO personal wiring.

### (No step) — Multi-tenant isolation (W8) — **dissolved by decision**
- Self-host-per-user makes cross-tenant leakage structurally impossible.
  No work unless you ever choose to run a hosted service.

---

## 3. The Gate (unchanged) — do NOT onboard a second human until ALL hold
- Tool execution sandboxed (STEP 5).
- Read-surfaces can't widen scope or trigger external sends unprompted —
  **W7 LIVE & registry-driven** (STEP 1), not just module-complete.
- Credentials encrypted at rest (STEP 3).
- Public codebase is a separate, restructured repo with no personal wiring (STEP 7).
- Browser runs cross-platform (STEP 6).
- ~~Per-user isolation~~ — **already satisfied** by self-host-per-user.

Status: W1 ✅, isolation ✅. Open: W7-live, sandbox, encrypted creds, clean repo,
cross-platform browser.

---

## 4. Capability score — before vs. after

Scored out of 10. "Now" = today's verified state (W1 done; W7 inert).
"All fixed" = STEPS 1–7 complete on a shipped, self-host-per-user product.

| Capability | Now | All fixed | Note |
| --- | :---: | :---: | --- |
| Harness / orchestration | 8 | **9** | sandbox + clean structure on a strong spine |
| Governance & safety | 9 | **10** | W7-live + sandbox + encrypted creds + fail-closed verifier = fully realized |
| Memory — governance | 9 | **9** | already near ceiling |
| Memory — retrieval intelligence | 5 | **8** | rerank + neighbor links + temporal; entity graph deferred |
| Agentic loop / autonomy | 5 | **8** | W1 done; native tool-calling + reachable tools to come; bounded by design |
| Model routing | 7 | **8** | cost-aware tier + fallback chains |
| Artifact quality (Office) | 8 | **8** | not a weakness |
| Distribution / usability | 3 | **8** | cloneable + installer + cross-platform browser; polish/adoption gate the last 2 |
| Engineering discipline | 8 | **9** | packages + tests/ + cross-platform CI |
| **Overall** | **7.0** | **8.5–9** | |

**Interim checkpoint** (after STEPS 1–4 only — the cheap, mostly-personal wins):
overall ≈ **7.5**. Governance rises to ~9.5 (W7 live), autonomy to ~6–7,
retrieval to ~7. The jump from 7.5 → 8.5+ requires the big pre-public rocks
(STEPS 5–7), which only pay off when you actually go public.

**Why not 10:** two ceilings are intentional, not gaps. Bounded autonomy is a
deliberate design choice that protects the governance moat (pushing it to 10
would trade away the differentiator). And distribution/retrieval can't be
bought with code alone — docs, real users, and an entity graph justified by
real scale are post-launch, time-and-adoption work.

---

## 5. One line for the next session

Wire W7 live and registry-driven **first** — it's the smallest remaining
severity-5 and it activates a defense that's already built but currently
protecting nothing. Then config-extract, keychain, memory rerank (all cheap,
all help the personal product today). Save sandbox/restructure for when a
public date is real. Don't onboard a second human until the Gate in §3 holds.
