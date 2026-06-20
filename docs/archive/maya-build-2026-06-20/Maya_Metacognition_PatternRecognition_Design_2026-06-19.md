# Maya — Pattern Recognition & Metacognition (Design Spec)
*Reviewer: Steward. 2026-06-19. The capability build behind "improve Maya without swapping the brain." Grounded in the real loop (`maya_harness/harness_llm_planner.py`) and the spine (`planner_facts.py` content-vs-control). This is a design to review, then hand to Codex — not yet code.*

---

## 0. The framing, made into engineering
The human-brain analogy is fine as intuition, but it has to cash out as code:
- **Metacognition** = the loop reasoning about *its own* process: is this working, why did that fail, how sure am I, should I change approach / abstain / escalate. It governs the loop.
- **Pattern recognition** = memory across episodes: "a task shaped like this has come up before — here's what worked / what failed." It feeds the planner.

Neither is magic, and neither is new authority. Both produce **suggestions and self-assessments**, never effects. The kernel still decides every effect. That's the rule the whole design hangs on.

---

## 1. What the loop has TODAY (verified in code)
- `plan_with_llm` → `choose_next_action` (one tool per step) → `verify_goal` → `synthesize_final_answer`, bounded by the 8-step budget. Reserved final step lands an honest answer.
- **Already present — the seeds:** `verify_goal` is **fail-closed** (only an explicit YES is "done"; ambiguity → False, loop stays open, budget prevents infinite). `synthesize_final_answer` is required to **name evidence gaps, never invent**. These are real metacognition primitives — keep and extend them, don't replace.
- **Missing:** (a) no **failure attribution** — the loop never asks *why* a step didn't help; (b) no **confidence** — verify is binary, so a near-miss and a total failure look identical; (c) no **strategy switch** — a repeated failure just repeats; (d) **stateless across episodes** — no memory of what worked before. choose_next_action is even biased "prefer finishing over gathering," i.e. biased to stop, not to diagnose-and-retry.
- **Spine already wired:** `planner_facts` are content-only (`control_eligible=False`); the kernel gates effects. So new inputs plug in as facts = safe by construction.

---

## 2. Metacognition layer (build FIRST — safer, higher leverage)
Reasons over Maya's *own* process; mostly internal, so low new attack surface. Four parts:

**2.1 Failure attribution (the missing reflex).** After each step, a hook classifies the step's outcome into a **closed, conservative failure taxonomy** (see §6 — the judgment call): e.g. `progressed`, `wrong_tool`, `bad_args`, `missing_info`, `gate_blocked`, `no_progress`. Emitted as a **metacognitive fact** (content-only, like planner facts) fed into the *next* `choose_next_action`. This is what turns "try again" into "try **differently**."

**2.2 Confidence, not just YES/NO.** Extend `verify_goal` to return a confidence + reason alongside the verdict (stay fail-closed: anything short of confident-YES is not "done"). Confidence drives the branch:
- confident-YES → done.
- low-confidence + budget left → **re-plan with a changed approach** (using the failure fact), not a blind repeat.
- low-confidence + no budget → **abstain honestly** (synthesize already names the gap — reuse it).

**2.3 Bounded anti-degeneracy (the "smart and bounded" part).** Track attempted (tool, args-shape, failure) tuples. **Forbid repeating an action that already failed the same way.** Add a **no-progress detector**: N steps with no attribution better than `no_progress` → stop and escalate rather than burn budget. This is what stops the loop from looping stupidly — the failure I warned about earlier, now guarded.

**2.4 Escalate, never fabricate.** When metacognition concludes "stuck / don't know," the move is **ask the owner or abstain**, never invent. Ties straight into the honesty axis.

**THE security invariant for metacognition (non-negotiable):** metacognition may only **lower or hold** privilege — abstain, escalate, re-plan, stop. It can **never raise** privilege or bypass the kernel. "I'm confident, so skip confirmation" is forbidden. A self-assessment is not authority; the kernel still decides every effect. High confidence changes *whether Maya tries*, never *what she's allowed to do*.

---

## 3. Pattern recognition layer (build SECOND — after the harness test exists)
Memory across episodes, feeding the planner. Higher value *and* higher risk, because it adds an untrusted-derived input to planning.

**3.1 Procedural/episodic memory.** Store per-episode traces: **situation shape → approach → outcome**. On a new task, retrieve similar past situations and surface "last time, tool-sequence X worked / approach Y failed" as a **planner fact** (a content suggestion). Rides existing memory infra (`maya_memory/`, `session_memory_store`, `skill_memory_store`) — a new *procedural* store keyed by task-shape features, not raw text.

**THE security invariants for pattern recognition (this is where it can go wrong):**
- **Store procedural SHAPE, not untrusted values.** A pattern may suggest "use the calendar tool, then summarize." It may **never** carry a concrete control value ("send to `<address from a past email>`"). Values are re-derived per episode under the kernel; patterns are about *method*, not *targets*.
- **Suggestions enter as content-only facts** (`control_eligible=False`). Even a **poisoned** pattern cannot choose an effect — the kernel re-gates every action. This is the laundering firewall.
- **Provenance-tagged.** A pattern learned from an episode that had untrusted influence / injection is flagged and quarantined from control, same as everything else.
- **No-resurrection.** A pattern shown wrong/superseded is not revived (reuse the W2 supersede discipline — `canonical_memory_supersede`).

**Why second:** pattern recognition is exactly a cross-episode laundering surface. It should not ship until **Step 0.5 (the harness test)** exists to *catch* a poisoned pattern trying to influence control. Build the test, then turn on the memory that the test guards.

---

## 4. The convergence (why this is the same object as Step 0.5)
The reflect → re-plan → verify → retry loop is **both** the capability engine and the security surface. Every retry reads more tool output = more injection exposure; every metacognitive re-plan is another decision that must run on facts, not raw untrusted instructions. So **the loop you're improving for capability is the loop the harness test measures for security.** Building this and testing it are one surface — the work compounds, it doesn't split. This is the concrete version of "harness engineering raises capability" — and it raises it honestly only if the same loop holds the line under attack.

---

## 5. Honest sequencing, risks, and ceiling
**Sequence:** metacognition (§2) → confirm on the harness test → pattern recognition (§3). Don't invert; §3 needs §2's discipline and the test's coverage.

**Real failure modes (named, with the guard):**
- *Degenerate loops / repeating the same mistake* → §2.3 anti-degeneracy (forbid repeat-failures, no-progress stop).
- *Error accumulation / context rot over long loops* → keep the budget; prune observations (the loop already caps to 6); confidence-gated early stop.
- *Cost/latency blowup* → each retry is real tokens; cap iterations, and only re-plan when attribution says it's worth it (not every step).
- *Pattern poisoning / laundering* → §3 invariants + ship behind the harness test.

**Honest ceiling:** this genuinely raises effective capability without a new model — a reflect-and-retry loop closes a real chunk of the 40%/60% utility gap that was *harness-gave-up*, not *model-can't*. But it is **not unbounded**: a smart loop can't make the base model reason about something it fundamentally can't, and naive looping degrades. The gain is real and large *and* it has a craft ceiling. Both true.

---

## 6. Send me this first (the one decision before building)
Like every prior step, one judgment call gates the rest: **the closed failure taxonomy** for §2.1 — the exact, conservative set of failure-reasons the reflector is allowed to emit (`progressed`, `wrong_tool`, `bad_args`, `missing_info`, `gate_blocked`, `no_progress`, …). Keep it **closed and small**, the way the source-trust registry was closed: an open free-text "reason" would let untrusted content narrate the loop's self-assessment and steer the re-plan. A fixed enum can't be hijacked into instructions. Lock the taxonomy (and the confidence thresholds that branch on it) before Codex wires a line — that's the piece everything downstream inherits.
