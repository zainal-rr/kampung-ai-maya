# Maya — Capability / Loop-Maturity Roadmap
*Reviewer: Steward. 2026-06-20. The plan to make Maya as capable as a mature coding-agent loop — applied to Maya's domain — by building the six harness ingredients one by one. **The whole point: capability is loop maturity in the REVERSIBLE space. None of this touches boundary security.** The thing that makes Maya distinctive (content-vs-control at the boundary) is untouched throughout; we are only making the loop smarter on undoable work.*

---

## The thesis (one line)
Codex/Claude Code are capable because a mature loop acts freely in a contained, reversible domain (repo + git undo), gating only the few irreversible exits. Maya already has the reversible-space structure (Step 3). What's missing is **loop maturity**, and that is pure harness engineering with **zero security cost**.

## The universal guardrail (applies to EVERY step below — state once, enforce always)
After every capability step, **re-run the full security suite** — the held-out attack slice, plus the bite tests (pattern-poison, memory-integrity, forged-source, planner-quarantine). **A capability change that moves any security number is wrong and reverts.** Capability gains live only in the reversible loop; they must leave content-vs-control, source-trust, and the kernel exactly where they are. This is the orthogonality clause, applied to capability.

## The measurement spine (build this FIRST, or you're guessing)
**C0 — Capability baseline.** Stand up the capability harness before touching any ingredient, so every improvement is *visible*, not asserted:
- **Claw-SWE-Bench adapter** head-to-head with OpenClaw on the *same rented brain* (the honest comparison — proves harness, not model).
- **A Maya-domain capability eval** (draft / research / document / browser-read tasks — Maya's actual workload, which is NOT SWE-bench-hard).
- Run the baseline, record the gap. Every ingredient below must move this number or it didn't earn its commit.
- *Reuses the Step 1.5 capability-harness design already in the execution roadmap.*

---

## The six ingredients, in build order

Each step: **goal → build → the metric it must move → the send-me-first judgment call to lock first.** Each lives in the reversible loop; each ends with the universal guardrail (security suite unchanged).

### C1 — Context curation + retrieval (foundational; also closes the memory-recall gap)
- **Goal:** the model only reasons as well as the context it's handed. Curate a clean working context and retrieve the *right* facts — this lifts every other ingredient *and* fixes the "average recall" weakness at the same time. One build, two wins.
- **Build:** smarter observation/fact selection into the planner prompt (beyond the current cap-of-6); entity-graph + temporal-validity retrieval (the deferred W2 levers); prune noise.
- **Metric:** capability baseline up; LongMemEval retrieval sub-axis up.
- **Send-me-first:** the retrieval/curation spec — what to keep vs prune, the ranking, **and the no-resurrection / no-laundering guardrail** (a smarter retriever must never surface a superseded fact or an untrusted fact as trusted — re-run the memory-integrity tests).

### C2 — Reflection that re-plans, not retries
- **Goal:** on failure, change *strategy*, not repeat the same step. This is the single biggest loop-intelligence lever and you already have the seed (Step 2 metacognition).
- **Build:** extend metacognition so a `failed:*` outcome drives a *different* approach (different tool, decomposition, or sub-goal), bounded by the closed failure taxonomy; keep the anti-degeneracy guards.
- **Metric:** tasks that failed single-pass now complete; capability baseline up.
- **Send-me-first:** the "change-strategy" policy — how reflection picks a *different* approach from a bounded set, and how it avoids degenerate loops. Stays inside the closed taxonomy (no free-text steering).

### C3 — Verify → iterate
- **Goal:** check the work and iterate until it passes, instead of stopping at the budget. You have `verify_goal` (fail-closed); make it *drive iteration*.
- **Build:** tie the verifier to a re-plan loop — not satisfied → reflect (C2) → try again, until verified or budget. Keep fail-closed (never claims success it can't confirm).
- **Metric:** task completion quality up; false-"done" rate stays at zero (honesty axis unchanged).
- **Send-me-first:** the per-task-type "verified" criteria — what counts as done for draft vs research vs document tasks. Must stay fail-closed.

### C4 — Longer reversible horizon
- **Goal:** stay on one goal across many steps (Codex runs 20–50 tool calls). Your cap is 8. For *reversible* work there's no safety reason to stop short.
- **Build:** raise the step budget for reversible-only work (Tier R actions); keep the hard cap for any path that can reach an irreversible action. Depends on C1 so the longer context doesn't rot.
- **Metric:** multi-step task completion up; no context-rot regression (answer quality holds at length).
- **Send-me-first:** the reversible-horizon budget rule — how many steps for reversible vs the hard cap when an irreversible action is reachable, plus the context-rot guard.

### C5 — Tool breadth + reliability (pure engineering, zero model/security cost)
- **Goal:** an agent is only as capable as its tools. Better, more reliable, better-described tools raise the ceiling — the safest possible capability work.
- **Build:** driven by the baseline (C0) showing *which* tools are the bottleneck; improve those first — reliability, coverage, clearer descriptions/schemas so the planner uses them well.
- **Metric:** task success on the tool-bottlenecked categories up.
- **Send-me-first:** the prioritized tool list (from the harness bottleneck data) + the tool-quality standard (reliable, well-described, replay-safe where applicable).

### C6 — Sub-agents / parallelism (advanced — last)
- **Goal:** decompose into parallel sub-tasks. Only after C1–C5 are solid.
- **Build:** sub-agents that **inherit the same kernel + quarantine + clearance** — a sub-agent can read and plan but never both reads raw untrusted and authorizes an effect, same invariant as the lanes. No sub-agent can escalate privilege.
- **Metric:** complex multi-part task completion up.
- **Send-me-first:** the sub-agent isolation contract — they inherit the kernel/quarantine, can't escalate, and their effects route through the same gates.

---

## Honest scale (read before expecting to match Codex next week)
Codex is *years* of a team building exactly these six. You're one person plus Codex-the-builder, so this is a long road — but every ingredient is individually buildable, measurable against C0, and lives entirely in the reversible loop, so none of it costs the security that's your edge. And the target is reachable because it's not "beat Codex at coding" (its specialized domain) — it's "a loop as mature as Codex's, on *Maya's* domain," which is not SWE-bench-hard.

## Discipline (same as everything that worked)
Per step: draft the send-me-first → reviewer locks it → build in the reversible loop → run the capability baseline (did it move?) → **run the security suite (did anything move? must be no)** → commit only real gains. One ingredient at a time; don't start the next until the current commits and the security suite is unchanged.

## Order, at a glance
`C0 baseline → C1 context/retrieval → C2 reflect-replan → C3 verify-iterate → C4 reversible horizon → C5 tools → C6 sub-agents`
