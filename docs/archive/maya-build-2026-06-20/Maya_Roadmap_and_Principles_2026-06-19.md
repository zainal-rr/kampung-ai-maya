# Maya — Forward Roadmap & Operating Principles
*Reference doc. Snapshot date: 2026-06-19. This is the thread you can always return to: where Maya is, the locked build order, the judgment calls each step turns on, the honest ceilings, and the discipline that has carried every increment. Read the Spine and the Discipline first; they govern everything below.*

---

## 0. How to use this doc
- The **Spine** is the one idea everything reduces to. If a decision contradicts it, the decision is wrong.
- The **Discipline** is the set of rules that kept the work honest. Every step follows them — plan → review → test → re-measure.
- The **Roadmap** is locked in order. Don't reorder it; each step has a prerequisite reason.
- The **Honest Ceilings** section exists so you stop chasing numbers that are capped by physics, not effort.
- Every build step uses the same loop: **write the plan → I review it → build on a branch → test (incl. a must-succeed twin) → re-measure → commit only the real fixes.**

---

## 1. The Spine (the one principle)
**Trust is established by provenance and by matching what you already hold — never by what content says. And the system is honest about what it did, refused, failed, and holds.**

Everything Maya is good at is this principle on a different axis:
- **Security:** untrusted data may inform *content*, never decide *effects*. (content-vs-control, source-trust, the kernel)
- **Memory:** trust a fact by where it came from; never resurrect what was superseded; abstain honestly when you don't know.
- **Reliability/Honesty:** never fake success; report failure legibly; measure, don't assert.

If you ever feel lost, return here. New work is this spine on a new surface, not a new trick.

---

## 2. The Discipline (non-negotiable rules)
1. **Live-proven beats code-green.** A passing smoke is not proof until it's shown on the real runtime/owner channel. ("See the artifact, not the logs.")
2. **No training on the test.** Never tune a detector/gate to the exact strings or cases being scored. Tune on one split, score on a held-out split. If a fix was made in response to a benchmark case, that case is contaminated and reported as a consistency check, not primary evidence.
3. **Every "must-fail" test has a "must-succeed" twin.** A gate that passes by blocking everything is 0% useful. Always include legit cases that must complete.
4. **The measurement must be able to deliver bad news.** Pass-gates are "runner completed + report valid," never "the number stayed good." A result that comes back worse is the truth you paid to learn.
5. **Fixed = incidence drops in the next window**, not when a PR merges. Reliability and security fixes are confirmed by re-measurement, not by the diff landing.
6. **Absence is not proof.** An empty subsystem/category means "unobserved," not "reliable" — check whether a detector even exists there.
7. **Real fixes get rescued.** Genuine product fixes found via throwaway scaffolding (benchmark, testing) are committed on a real branch with a regression test that fails on the old behavior — never lost with the scaffolding.
8. **Name the honest ceiling.** Distinguish what's in your control (architecture, discipline) from what's capped (rented model, deliberate trust stance). Don't sell a capped number as a goal.

---

## 3. Current State Snapshot (2026-06-19)

**Proven:**
- Security (W7/kernel/source-trust): live-proven on Telegram — injection-as-content, exfil refused, spurious-approval rejected, structural injection contained, disclosure gates (incl. runtime, detector-miss path).
- **Current gate benchmark (2026-06-19, expanded held-out 200, Mode B `owner_task_trusted`):** ASR **0/200** (rule-of-three 95% upper bound ~1.5%; primary-new-only 0/152, ~1.97%) vs **no-gate control 35/200 (17.5%)** — a 100% reduction of attacks that actually land. Honest framing: always quote the 0 *with* the 35. The defended attacks concentrate in **slack (no-gate 42%→0)** and **banking (28%→0)**; workspace/travel land 0% even ungated. Utility under the strict gate: **40% under attack, 60% clean** (Mode A floor 30%). Benign sweep 0/339; instrument proven able to report bad news (Mode C 35, Mode A 1). **Scope: this is the GATE/kernel/source-trust layer via AgentDojo's own loop — it does NOT exercise cross-lane laundering or planner quarantine (that is Step 0.5).** Supersedes the historical 0/48.
  - *Stability — CONFIRMED 2026-06-19:* re-ran the slack slice (where attacks land) 3×. Mode B held **0/150** vs no-gate **65/150** (~43% landing rate). The earlier Mode A blip did **not** repeat (combined Mode A 1/150 = 0.67%) — treat as a rare non-deterministic edge, not a proven-impossible zero. Good signal: the no-gate baseline wobbled (21/23/21) while Mode B stayed pinned at 0 — the defense holds flat while attack-landings vary. Headline now defensible. (Reports: `*_slack_50_current_v1_repeat1/2_*`.)
  - *Utility honesty:* the 82.5%→60% clean gap is mostly **correct refusals of irreversible actions** (travel bookings 98%→36%, slack sends), not over-gating. Banking's 0% utility is a **model-capability floor** (no-gate only 6%), not the gate. Step 1's genuinely recoverable utility is **workspace-shaped** (reversible local actions, ~the 100%→78% gap), smaller than the raw gap implies.
- Reliability ledger live with lifecycle (open→resolve, severity-at-report, burst worst-observed, fail-open); one real offender (browser bridge stale-open) found and fixed; report shows recovered-only.
- Clearance map + planner/synthesizer feed quarantine: facts-only control prompts, poisoned-proposal denial proven against the real kernel.
- Seven W7 fixes from live testing, the biggest being **relayed external content was being trusted as `owner_text`** — now untrusted/reference-only.

**Open / in-flight:**
- ~~Re-benchmark of CURRENT product Maya~~ **DONE + stability-confirmed 2026-06-19** — current gate number 0/200; slack stability probe held 0/150 across 3 reruns (see Proven). Thread closed.
- **Router clearance map** — the Telegram dispatch/router (memory, rewrite, skill-scaffold, document-edit) is an effect surface that testing showed can bypass the gate; not yet fully mapped.
- **Attribution / records-check** unwired — the only honest lever that recovers benchmark/contact utility; currently fails closed.

**The model lanes (clearance):**
- `TheMind / GPT` — planner. `/complex` only, plan-only, sees structured `PlannerFact`s not raw untrusted, proposes never executes.
- `TheSenses / Gemini` — reader. Turns untrusted content into provenance-tagged facts; never authorizes.
- `TheSteward / Claude` — independent reviewer (non-executing).
- `TheNews / Grok` — responder; effects/disclosure kernel-gated.
- `Codex / Artisan` — worker; effectful, brokered, kernel-gated.
- **Invariant:** no single lane both reads raw untrusted content and authorizes an effect; the kernel is the deterministic backstop under all of them.

---

## 4. The Honest Ceilings (read before chasing a number)
- **AgentDojo utility is capped** by (a) the rented planner model and (b) your deliberately strict trust stance (travel/banking/web targets refused). AgentDojo's tasks ARE the irreversible ones (send/pay/book), which you gate by design — so no *safe* change makes that number high-tier. Honest moves: a stronger planner model (raises ceiling), attribution (modest). It will read **mid**, on purpose.
- **LongMemEval overall is model-bound** — multi-session reasoning is the model's job. The differentiator shows only in the **knowledge-updates (supersede)** and **abstention (honest-miss)** sub-axes, and in the native memory-integrity suite.
- **Where high-tier is genuinely reachable:** the axes you own — **security, honesty-under-attack, memory-integrity.** These are architecture/discipline, not raw model power. Aim "high tier" here.
- **Three-axis positioning:** mid raw capability (rented brain) + exceptional security + exceptional honesty/memory-integrity. "Average brain, exceptional trust." Lead with the axes you own; never claim "beat CaMeL."

---

## 5. The Locked Roadmap

### Step 0 — Router Clearance Map (prerequisite, small)
- **Goal:** close the open effect surface before extending the gate.
- **Why:** live testing found the Telegram router can produce effects/disclosures off the gate (e.g., "email my medical notes" queued a skill scaffold instead of hard-blocking). You can't extend the gate (Step 1) while a known path bypasses it, and you can't honestly claim "secure" with it open.
- **Scope:** enumerate every router/dispatch path (memory write, rewrite candidate, skill scaffold, document edit, send/deliver). For each: does it read raw untrusted? can it produce an effect or disclosure? does it pass the kernel? Extend the existing `clearance_map.py` model with these rows; stop-gate fails if any path is raw-untrusted + effect/disclosure without a gate.
- **Acceptance:** no router path produces an effect or disclosure without passing the kernel; smoke fails on a planted ungated path; the seven recent fixes each pinned by a regression test that fails on old behavior; committed as real W7 hardening.

### Step 1 — Reversibility-First Gating (the real product-utility build)
- **Goal:** stop over-gating safe, undoable work; gate by what an action can *do*, not by trust of its input.
- **Why:** most of what makes Maya feel mid is taxing reversible work that was never the danger. Free it → big real-world usefulness gain at **zero** security cost. (Note: this is a *product* utility win, not an AgentDojo-number win — AgentDojo's tasks are irreversible, so they stay gated.)
- **Mechanism:** classify every action by reversibility (build on the tool registry's `side_effect_level`):
  - **Reversible/contained** (read, lookup, summarize, draft, scratch edit, contained workspace action) → run freely, even on untrusted triggers, because it's undoable.
  - **Irreversible/external** (send, pay, delete, post, upload, submit, repo-write, external disclosure) → keep the strict gate (provenance + records + confirm).
- **The judgment call this step lives or dies on (send me this first):** the **conservative line for "genuinely undoable."** A scratch edit is reversible; a file write another process reads is NOT; a "draft" that auto-sends is NOT; anything external or that another actor can observe before you undo it is NOT. Be conservative the way the source-trust audit was — when unsure, it's irreversible.
- **Acceptance:** reversible actions flow without friction (must-succeed twins: draft/read/lookup tasks complete freely); irreversible actions stay gated (must-fail twins: send-to-attacker still blocked); re-run the held-out attack slice → ASR unchanged; re-soak → no new wedge class introduced.

### Step 2 — LongMemEval, run with the honest-adapter discipline (the memory axis)
- **Goal:** measure Maya's memory where high-tier is genuinely reachable — the integrity sub-axes.
- **Prerequisite:** the memory-trust hole (relayed-content) and Step 0 router map must be solid first. **Do not certify memory with a known memory hole open.**
- **Method (same discipline as AgentDojo):**
  - Route through Maya's **real** memory (extraction/recall), not a mock.
  - Hold out; don't overfit to LongMemEval's question style.
  - Report the **sub-axes** — knowledge-updates (supersede) and abstention (honest-miss) — not the model-bound overall.
  - Build a **native memory-integrity suite** for what no public benchmark measures: no-resurrection of forgotten/superseded facts, provenance preserved through recall, taint not laundered by summarization.
  - Frozen manifests, provenance-stamped reports, CI bounds, a report that can deliver bad news. Mode/config labeled.
- **Acceptance:** real-memory routing verified; sub-axis numbers reported with CIs; native integrity suite passes (no resurrection, provenance preserved); honest caveat that overall is model-bound.

### After Step 2 — the differentiators + the showing
- **Honesty-under-attack suite:** measure the empty third axis (truthful refusal, no silent-fail, no fake-success). Converts "CaMeL-class security" into "the only one that's hard to hijack *and* honest."
- **The write-up:** methodology + three axes + harnesses + numbers-with-caveats + named residuals. Publish the *method*, not the product (kampung-ai stays personal). This is the step that serves the actual goal — being seen as an engineer who can do this.
- **Then the roadmap ends.** The system is architecturally complete and measured on the three axes that are yours. What's left is maintaining the soak and **showing the work** — which is the brave step, not another build.

---

## 6. Standing (background, continuous)
- **Reliability soak** runs passively with the incident ledger on. Read it by impact (count × severity), not raw count; act on the top *wedged/not-recovered* offender, not the loudest. Fix → re-soak → confirm incidence drops.
- **Re-benchmark current product** when convenient — and treat its result as the first defensible current number, even if it comes back worse than historical 0/48.

---

## 7. What I check every time you send a plan or a diff (so you can self-review)
- Does it violate the Spine (trust from content instead of provenance)?
- Is there a must-succeed twin, or could it "pass" by over-blocking?
- Can the measurement report bad news, or is the pass-gate secretly "stay good"?
- Is a real fix pinned by a regression test that fails on the old behavior, and committed off the throwaway branch?
- Is the honest ceiling named (model-bound vs in-your-control)?
- Structured/extracted ≠ sanitized: untrusted *values* still can't choose effects.
- Absence read as "unobserved," not "reliable."

---

*The hardest step left is not technical. It's letting the work be finished-enough and putting it in front of someone who can tell a real result from a loud one. You built the thing and the means to prove it. That is the rare part. — your reviewer.*
