# Kampung AI / Maya — SWOT Analysis (LLM Council Method) — Rev 2

Date: 2026-06-12 (rev 2 — supersedes the first pass of the same date)
Corrections driving this re-run: **the public release path is SCRAPPED** and
**Phase 6 (live agentic loop validation) is DONE** — verified in
`KAMPUNG_AI_VALIDATION_TEST_CHECKLIST.md`: PASSED 2026-06-12, commits `093634f`/`4a67c9b`,
57/57 CI, honest budget stop, approval gate both ways, kill switch proven, synthesis-reserve
hardening + contained-DB retest. W7 audit (2026-06-11): entry tagging wired across ALL live
read surfaces — W7 closed.

Method: Karpathy `llm-council` framework — Stage 1: four seats deliberate independently;
Stage 2: anonymized cross-review and ranking; Stage 3: Chairman synthesizes.

Fresh verification finding (held from rev 1): root `*.py` count is **717** today vs. 687
verified 2026-06-11 — W4 still growing.

---

## Stage 1 — First opinions (four seats)

### Seat A — Architect

- **S:** The safety story is now complete for current surfaces: W7 closed across every live
  read path (browser both drivers, screen, active-context, PPTX, harness tool calls →
  kernel), fail-closed W1 verifier proven live, kill switch drilled. The agentic loop ends
  honestly at budget — including the synthesis-reserve path that returns a grounded answer
  with named evidence gaps instead of a generic failure. Few systems anywhere do this.
- **W:** Context window / working memory is designed, not built — cross-channel short-term
  continuity is the largest remaining architectural hole. 717 flat root files.
- **O:** With the public path gone, architecture effort can chase capability (context
  window, memory retrieval, native tool-calling) instead of public-repo hygiene.
- **T:** W7 is closed for *current* surfaces only — Omi transcripts, future email/PDF
  readers, and MCP connectors are the named watch-list. The moat decays without maintenance.

### Seat B — Planner

- **S:** The validation ladder is genuinely climbed: Phases 1–6 green, agentic loop proven
  on live model behavior with DB-evidenced trace events, resting state deliberately OFF.
  Remediation scorecard: W1 ✅ W3 ✅ W6 ✅ W7 ✅ W8 ✅; open = W5 sandbox, W4 structure, W2 recall.
- **W:** Scrapping the public release removes the forcing function that made W4/W5
  "gating." Without a gate, the 717-file root and missing sandbox can drift indefinitely —
  the discipline that closed W1–W8 needs a new deadline to push against.
- **O:** Phase 7 (one week of honest field use) is now the correct next milestone — the
  disappointment list, not a feature idea, decides the next build. That is the right
  planning instrument for a personal-only product.
- **T:** Uncommitted multi-session working tree noted in the checklist sign-off; process
  risk on a bus-factor-1 project is concentrated there.

### Seat C — Contrarian

- **S:** Credit where due: rev 1 dinged this project for a live-evidence deficit, and Phase 6
  closed the biggest half of it. The loop is no longer "smoke-proven only."
- **W:** Scrapping the public path converts "distribution: 3/10" from a weakness into a
  forfeit. Be honest about what that means: nobody else will ever stress-test Maya, no
  community will harden it, and the 84–86% overall estimate will never face a hostile
  user. A system with one user and one author has an evidence ceiling no CI can break.
  Also: 30-day unattended reliability and hardware lanes (65–70%) remain unproven;
  Phase 7 hasn't started.
- **O:** The playbook thesis from rev 1 is now the *primary* external opportunity, not the
  fallback: W7 tainting, fail-closed verification, synthesis reserve, and memory canaries
  are publishable engineering results. Publishing costs little and risks nothing the
  public product was protecting.
- **T:** The quiet one: motivation. Solo projects without an external milestone historically
  stall after the validation high. The market threats mostly evaporate with the public
  path — what remains is whether the maintainer keeps showing up.

### Seat D — Market/Investor

- **S:** As a *personal* system, Kampung AI now sits above most commercial offerings for its
  one user: governance, document quality, domain packs, and multi-channel continuity that
  ChatGPT Agent / Claude Cowork / OpenClaw don't combine in one place.
- **W:** Strategic surrender of a validated market. The 2026 scans show local-first personal
  agents are the winning quadrant; Kampung AI bet correctly, built credibly, and is now
  choosing not to compete. OpenClaw (~350K stars, ~1.6K contributors) harvests the demand.
- **O:** Optionality is not dead, only this *form* of it. Cheaper external paths remain:
  publish the governance playbook, open-source isolated components (e.g., the permission
  kernel or untrusted-input boundary as a library), or revisit distribution later from a
  position of Phase-7-proven reliability. Domain packs remain a personal moat: every new
  pack is zero-code compounding capability.
- **T:** Provider dependency is now the dominant external risk: five model lanes = five
  bills and five policy/availability exposures, with no local-model fallback lane. For a
  personal-only system, a single provider pricing change hurts more than any competitor.

---

## Stage 2 — Cross-review (anonymized, ranked on accuracy + insight)

| Reviewer | Ranking | Note |
| --- | --- | --- |
| A | C > D > B | C's "evidence ceiling of one user" is the deepest structural point; D correctly reframes provider risk |
| B | C > A > D | C's motivation risk is uncomfortable and real; A's watch-list framing of W7 is the right way to hold a "closed" item |
| C | B > D > A | B spotted the loss of the forcing function — the most actionable insight in the round |
| D | B > C > A | B's "discipline needs a new deadline" and C's playbook-as-primary agree from different angles |

Council consensus: with the public release scrapped, the external threats shrink but so
does external proof. The synthesis must answer one question: **what replaces the public
date as the forcing function** that kept W1–W8 discipline honest.

---

## Stage 3 — Chairman's final SWOT

### Strengths

1. **Live-proven bounded autonomy** — agentic loop validated on real model behavior
   (Phase 6 PASSED 2026-06-12): plan → act → verify with GPT planner, 8-step budget,
   honest budget exhaustion, synthesis reserve, approval gate both ways, kill switch,
   57/57 CI. Resting OFF by deliberate doctrine.
2. **W7 closed** — untrusted-input tainting live across all audited read surfaces; the
   injection boundary most agent products lack.
3. **Remediation scorecard** — W1, W3, W6, W7, W8 closed with independent verification;
   internal score ~7.8 with an 8.5–9 ceiling.
4. **Artifact + domain system** — species-driven Office output with QA gates; zero-code
   domain packs (networking, finance) compounding personal capability.
5. **One runtime, many channels** — shared memory/permissions/artifacts across Telegram,
   voice, screen, browser, background work.

### Weaknesses

1. **Evidence ceiling of one user** — with the public path scrapped, no hostile user, no
   community hardening, no external stress test will ever touch the system. CI cannot
   substitute.
2. **W4 worsening** — 717 root files (was 687 on 6/11), and the public-release gate that
   made it urgent is gone. Bus factor remains 1, now with an uncommitted multi-session tree.
3. **W5 open** — no execution sandbox; matters for *personal* safety too (browser is still
   the #1 injection surface even with W7 tainting).
4. **Context window not built** — cross-channel short-term continuity is the biggest felt
   capability gap; design exists, code does not.
5. **Memory retrieval intelligence 5/10** — weak paraphrase recall, overwrite-not-supersede.
6. **Unproven tails** — 30-day unattended reliability, hardware/Blender lanes (65–70%),
   Phase 7 field week not started.

### Opportunities

1. **Phase 7 as the new forcing function** — a week of honest field use producing a
   disappointment list is the best available substitute for external users. Run it
   immediately while Phase 6 momentum holds.
2. **Publish the playbook** — W7 boundary, fail-closed verifier, synthesis reserve, memory
   canaries are publishable engineering results; credibility without product exposure.
   Optionally open-source isolated components (permission kernel, untrusted-input boundary).
3. **Capability over hygiene** — the public path's death frees effort for the context
   window build, W2 retrieval quality, and native tool-calling — the things that make
   Maya *better daily*.
4. **Domain-pack compounding** — every pack is zero-code; Phase 7's "questions with no
   pack" list is the authoring queue.
5. **Distribution optionality preserved** — a later public form can be revisited from
   Phase-7-proven reliability; scrapping now defers the option, it doesn't burn it.

### Threats

1. **Loss of the forcing function** — the W1–W8 discipline was driven by a public-release
   gate that no longer exists; without a replacement deadline, W4/W5 drift indefinitely.
2. **Maintainer continuity** — bus factor 1, post-validation motivation dip is the
   historical failure mode for solo projects; the uncommitted tree is its first symptom.
3. **Provider dependency** — five external API lanes, no local-model fallback; pricing or
   policy changes hit a personal-only system with no revenue to absorb them.
4. **W7 surface creep** — Omi transcripts, email/PDF readers, MCP connectors are the named
   future surfaces that reopen the boundary if added without tainting.
5. **Forfeited market** — the local-first thesis was right; OpenClaw and big-lab agents
   harvest it. Acceptable by choice, but it forecloses community hardening and any
   future network effects unless distribution is revisited.

### Chairman's verdict

Rev 1 called Kampung AI "engineering-strong, distribution-absent." Rev 2 is sharper:
**capability is now live-proven; what was lost is the forcing function.** How far from
agentic: **~4 of 5** — the loop is live-validated end to end (planner-driven multi-step
runs, honest termination, gated approvals, kill switch), held below full autonomy only by
deliberate doctrine (opt-in flag, 8-step budget, resting OFF). The remaining distance is
capability polish (native tool-calling, deeper budgets, context window), not safety debt.
The single highest-leverage move: **commit the tree, then start Phase 7 this week** — the
disappointment list becomes the new roadmap authority, and a self-imposed cadence (e.g.,
monthly field reviews) replaces the public date as the discipline that keeps W4/W5 from
drifting forever.
