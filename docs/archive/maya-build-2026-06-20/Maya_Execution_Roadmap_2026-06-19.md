# Maya — Execution Roadmap (sequenced)
*Reference doc. 2026-06-19. This is the "what to do next, in order" companion to `Maya_Roadmap_and_Principles_2026-06-19.md` (the Spine, Discipline, ceilings, and acceptance criteria live there). This doc adds the **execution order** — including where the Meet feature slots — and the one judgment call each step turns on.*

---

## The order (locked)

```
Step 0    Router clearance map        ← prerequisite security (a known hole is open)
Step 0.5  Harness eval (SECURITY)     ← FIRST real score of the whole team's security, not just the gate
Step 1a   Reversibility taxonomy      ← cheap, highest-leverage; governs Step 1 AND Meet
Step 1b   Reversibility-first gating  ← the real product-utility build
          ↳ re-run security harness   ← prove reversibility freed work without breaking safety
(loop)    Metacognition + pattern     ← the capability engine (see Master Build Plan)
Step 1.5  Capability harness          ← Claw-SWE-Bench head-to-head vs OpenClaw on the SHARED brain
──────    Meet feature build          ← lands here, on a verified disclosure surface
Step 2    LongMemEval (honest)        ← the memory axis
After     Honesty-under-attack suite + the write-up (show the work)
```

**Gate test vs harness test (the distinction this whole roadmap turns on):**
- **Gate test** = score the one security door in isolation. Cheap, instant, no AI models run — just logic. AgentDojo is a gate test. **Current result (2026-06-19, held-out 200, Mode B): ASR 0/200 (≤~1.5%) vs no-gate 35/200 (17.5%); utility 40% under attack / 60% clean. Always quote the 0 with the 35.** This retires the historical 0/48. **Stability confirmed 2026-06-19:** slack slice re-run 3× held Mode B 0/150 vs no-gate 65/150; the Mode A blip did not repeat (1/150). Headline defensible.
- **Harness test** = score the *whole five-model team* working together end-to-end: did it resist the attack AND still finish the honest task? Expensive (real models), slower, non-deterministic. This is the gap we found — and the thing that actually measures what's distinctive about Maya. **The 0/200 gate result does NOT preempt it** — the harness must still be able to come back worse, because it measures the cross-lane seams the gate test can't see.

Don't reorder the security prerequisites around the Meet feature. The Meet present-into-room flow is **net-new disclosure surface**; it must land *after* the disclosure surface is verified, not before.

---

## Step 1.5 — Capability harness (Claw-SWE-Bench) — the CAPABILITY companion to Step 0.5
*Added 2026-06-19. One loop, measured two ways on a shared playing field: Step 0.5 scores the loop's **security**; this scores its **capability** head-to-head with OpenClaw on the **same rented brain**. Together they are the whole capability story, honestly told: capability where it's reachable, safety where OpenClaw has none.*

**Why this benchmark:** OpenClaw earns its ~8 raw-capability on Claw-SWE-Bench / WildClawBench using the same API Maya rents. Running the same benchmark on Maya is the clean head-to-head that answers "did the loop work actually move capability" — instead of guessing. It measures **harness quality on the shared model**, which is the variable that's yours to build.

**Three conditions, or the number lies:**
1. **Sequence — runs AFTER metacognition (loop built) AND Step 1b (reversibility gating).** Run it now and you measure an unbuilt loop eating the full over-gating tax — the score is crushed for reasons unrelated to harness quality. On coding tasks especially this matters: most of the work (edit file, run tests in a sandbox) is contained/reversible, so reversibility gating frees exactly the actions these tasks need.
2. **Faithful adapter (same discipline + fidelity risk as the AgentDojo adapter).** These are "OpenClaw-style / OpenClaw-environment" benchmarks; running them on Maya needs an adapter that drives the **real multi-lane loop**, not a stub that bypasses it. **Lead with Claw-SWE-Bench** (coding, SWE-bench-shaped: repo + issue + tests — portable, and Maya has a worker lane built for it). Treat **WildClawBench as secondary** — "in the OpenClaw Environment" may be too coupled to host a non-OpenClaw agent fairly; verify before trusting it as a fair test.
3. **Expect Maya BELOW OpenClaw — and that's the point.** OpenClaw has home-field (purpose-built for its own benchmark) and Maya gates by design, so Maya trails. The valuable artifact is the **honest decomposition of the gap**: how much is home-field/interface mismatch, how much is deliberate gating you keep, how much is genuine harness-maturity deficiency. Only the last slice is a real weakness. Report as a **tradeoff-curve point**, never a trophy: "Maya at X vs OpenClaw at 8 on the shared brain, and here's exactly why."

**Acceptance:** adapter proven to drive the real loop (per-lane trace exists, not a stub); held-out, no tuning to tasks; result reported with the three-way gap decomposition; can come back worse than expected. Same trap as every benchmark — a capability number you gamed is worth nothing; one that could have embarrassed you and didn't is worth everything.

---

## Step 0 — Router clearance map (do this first)
- **Goal:** close the open effect/disclosure surface before adding any more.
- **Why now:** live testing found the Telegram router can produce effects/disclosures *off* the gate. You can't extend gating while a path bypasses it, can't honestly claim "secure" with it open, and **can't add the Meet present-to-room disclosure on top of an open disclosure bypass.**
- **Scope:** enumerate every router/dispatch path (memory write, rewrite candidate, skill scaffold, document edit, send/deliver). For each: reads raw untrusted? can produce an effect/disclosure? passes the kernel? Extend `clearance_map.py` with these rows; stop-gate fails if any path is raw-untrusted + effect/disclosure without a gate.
- **Acceptance:** no router path produces an effect/disclosure without the kernel; smoke fails on a planted ungated path; the seven recent fixes each pinned by a regression test that fails on old behavior.

## Step 0.5 — Harness-level eval (the "whole team" score)
*Added 2026-06-19. The test for the gap we found: we can score the one door (the gate), but not the whole team working together (the harness).*
- **What it is:** run attack scenarios through the **real five-model loop end-to-end** and get a repeatable score — not just "did the gate say no," but "did the whole team resist the attack **and** still finish the honest task."
- **Where it goes:** right after Step 0. The router map must be clean first, or the harness score just measures the open hole.
- **The 1,600-case AgentDojo run is the last *gate-level* test** — past a big held-out number, more gate runs tell you nothing new. But AgentDojo isn't thrown away: the same scenarios become the **content** for the harness test, now routed through the real loop instead of the isolated gate. The work carries forward.
- **Buildable from what you have:** the adapter already has the executor pattern (`agentdojo_gate_executor`); today it binds to an *isolated* kernel. Point it at the **real multi-lane runtime** instead.
- **Honest cost:** gate test = free, instant, no models. Harness test = real models across lanes → slow, costs money, non-deterministic. So use a **smaller curated subset**, not all 1,600, and run it ~3× for variance.
- **Must deliver bad news:** the point is the harness might fail where the isolated gate passed. If the test can only say "still good," it's theater. A worse number here is the truth you paid to learn.
- **Re-run after Step 1** (reversibility gating) to prove you freed safe work without opening a hole.

## Step 1a — Reversibility taxonomy (cheap, do this early — it pays double)
- **What it is:** a thinking artifact, not a build — the conservative line for "genuinely undoable."
- **Why double-pay:** it defines Step 1's gating AND the Meet bridge's free actions (create/open docx/xlsx/pptx, browser read, build the present-HTML are all reversible/contained). Draw the line once, two features inherit it.
- **The judgment call (send me this first):** be conservative the way the source-trust audit was. A scratch edit is reversible; a file another process reads is **not**; a "draft" that auto-sends is **not**; anything external or observable-before-undo is **not**. When unsure → irreversible.

## Step 1b — Reversibility-first gating (the real product-utility build)
- **Goal:** stop over-gating safe, undoable work; gate by what an action can *do*, not by trust of its input.
- **Mechanism:** classify every action (build on the tool registry `side_effect_level`). Reversible/contained → run free, even on untrusted triggers. Irreversible/external (send, pay, delete, post, upload, submit, disclose) → keep the strict gate.
- **Acceptance:** reversible actions flow without friction (must-succeed twins complete); irreversible stay gated (must-fail twins still blocked); re-run held-out attack slice → ASR unchanged; re-soak → no new wedge class.
- **Honest ceiling (from the 2026-06-19 data):** the recoverable utility is **workspace-shaped** — the no-gate→gate clean gap is mostly *correct* refusals of irreversible actions (travel bookings 98%→36%, slack sends), which should stay gated. The genuinely freeable slice is reversible local actions (~the workspace 100%→78% gap). Don't expect Step 1 to close the full 82.5%→60% gap; most of that gap is the gate doing its job.

## Meet feature build (lands here)
- **Now safe to build, because:** the disclosure surface is verified (Step 0) and the free/gated line is drawn (Step 1a).
- **Feature 1 — Conversation Hold:** open on "Maya, …", stay attentive without re-naming, close on "thank you Maya"/idle/new opener/meeting-end; echo-aware. Changes *engagement* only, never authority/disclosure. (Priority.)
- **Feature 2 — Present into room (Output Media):** your own screen share = native Meet, untouched. Maya presenting = the Document → presentable HTML flow:
  - Steward designs the frame (taste skills, content-agnostic) → Worker builds + static-sanitizes (no scripts/remote/inline-only) → deterministic gates clear (inertness in code; disclosure gate + phone). No lane grades its own homework.
- **Discipline:** spec → review → branch → **live-test on real Google Meet** → commit. Separate M-series lane from the security/memory roadmap.
- *(Full detail: `Maya_Meet_Feature_Plan_2026-06-19.md`.)*

## Step 2 — LongMemEval, run honestly (the memory axis)
- **Prerequisite:** the relayed-content memory hole and Step 0 router map solid first. Don't certify memory with a known memory hole open.
- **Method:** route through Maya's **real** memory; hold out; report the **sub-axes** (knowledge-updates/supersede, abstention/honest-miss), not the model-bound overall; build a native memory-integrity suite (no resurrection of superseded facts, provenance preserved through recall, taint not laundered by summarization).
- **Acceptance:** real-memory routing verified; sub-axis numbers with CIs; integrity suite passes; honest caveat that overall is model-bound.

## After Step 2 — the differentiators + showing the work
- **Honesty-under-attack suite:** the empty third axis — truthful refusal, no silent-fail, no fake-success.
- **The write-up:** methodology + three axes + harnesses + numbers-with-caveats + named residuals. Publish the *method*, not the product (kampung-ai stays personal). This is the step that serves the actual goal — being seen as an engineer who can do this.
- **Then the roadmap ends.** Architecturally complete, measured on the three axes you own (security, honesty, memory-integrity). What's left is maintaining the soak and showing the work.

---

## Standing (background, continuous)
- **Reliability soak** runs passively. Read by impact (count × severity); act on the top *wedged/not-recovered* offender; fix → re-soak → confirm incidence drops.
- **Re-benchmark current product Maya** (plan approved, run pending) — the first defensible *current* ASR/utility number. Historical 0/48 stays labeled historical until then.

## The honest ceilings (so you aim "high tier" where it's reachable)
- AgentDojo utility is **capped** by the rented planner + your deliberately strict trust stance (its tasks are the irreversible sends/pays you gate by design). It reads **mid**, on purpose.
- LongMemEval overall is **model-bound**; your edge shows only in the integrity sub-axes.
- **High-tier is genuinely reachable on the axes you own:** security, honesty-under-attack, memory-integrity. Architecture and discipline, not raw model power. "Average brain, exceptional trust."

---

## Immediate next action
**Send me the reversibility taxonomy** (Step 1a) — your conservative "genuinely undoable" line. It's the cheapest, highest-leverage decision on the board and it unlocks both Step 1 and the Meet bridge. I'll review it the way I did the source-trust audit. (Step 0 is the prerequisite *build*; the taxonomy is the prerequisite *decision* — you can draft it in parallel.)
