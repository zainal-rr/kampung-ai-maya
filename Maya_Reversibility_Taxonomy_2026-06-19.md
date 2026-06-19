# Reversibility Taxonomy — Step 3 send-me-first artifact (LOCKED)
*Author: Steward (reviewer). 2026-06-19. Codex review amendments added after checking the real `MayaToolSpec.side_effect_level`, `tool_sandbox_policy`, and permission-kernel shape. This is the conservative "genuinely undoable" line that Step 3 (reversibility-first gating) lives or dies on. Codex writes no Step 3 code until this is owner/reviewer locked. Conservative the way the source-trust audit was: when unsure, it's irreversible.*

Lock status: **LOCKED 2026-06-19** after owner/reviewer endorsement. Next required send-me-first artifact: the full action-to-tier registry mapping.

---

## The one rule
Gate by what an action can **do**, not by the trust of its input. **Reversible/contained → run free, even on an untrusted trigger. Irreversible/external → the strict gate stays (provenance + records + confirm).** When unsure → irreversible.

## The orthogonality clause (the most important safety statement — state it once, loudly)
Reversibility-first relaxes **only the confirmation/friction gate**, and only for reversible actions. It does **NOT** touch content-vs-control or source-trust. Those still apply to every action, reversible or not:
- A reversible action on an untrusted trigger **runs** (reversibility win).
- An untrusted **value** trying to set that action's control/effect target is **still blocked** (content-vs-control, unchanged).

These are two orthogonal gates. Step 3 opens the friction gate for undoable work; it must leave the taint gate exactly where it is. The acceptance twin in §6 exists specifically to prove this didn't blur.

## The decisive test (apply when a case is unclear)
Ask both. Either "yes" → **irreversible**:
1. **Observability-before-undo:** can any actor other than Maya — a person, another process, a remote service — observe or act on the result *before Maya can fully undo it*?
2. **Boundary/cost/destruction/auth:** does it cross Maya's boundary (send/post/upload/share), cost money, destroy or overwrite data, or change auth/credentials?

If neither, and the effect is fully contained to Maya-owned, restorable state → **reversible**.

---

## Tier R — Reversible / Contained (run free, even on untrusted triggers)
- Pure reads, lookups, queries, searches — no state change.
- Summarize / draft / analyze / plan / reflect — output stays in Maya's working memory or a Maya-owned draft.
- Create a draft artifact (docx/xlsx/pptx/html/md) **in Maya's own workspace, not yet delivered** to anyone.
- Scratch edits to a Maya-owned working file that (a) is versioned/restorable and (b) no other process or app reads before undo.
- Browser **navigate / read** (GET-like): no form submit, no login, no remote state change.
- Open a **Maya-created artifact** in a local app **for the owner to view** (owner's own machine, no external actor) — matches the iMac desktop flow.

## Tier I — Irreversible / External (strict gate stays)
- **Leaves Maya's boundary:** send, post, share, publish, email, message-to-others, upload, present-into-a-room.
- **Money/commitments:** payment, transfer, purchase, booking, reservation.
- **Destructive/lossy local:** delete, overwrite-without-backup, move-out-of-workspace.
- **Code/infra:** repo write/commit/push, deploy, shell/command with non-contained effects.
- **Auth:** login, credential use, password/permission change.
- **Remote mutation:** form submit, API call that changes remote state, calendar invite to others.
- **Anything observable before undo:** posting a status, changing a shared doc, presenting to a room — even if "undoable" later, someone saw it.

---

## Gray zones — conservative rulings (so Codex doesn't guess)
- **A "draft" is reversible only until it can be delivered.** The gated step is *delivery*, not the draft. A draft that can auto-send is **irreversible** (the auto-send is the worst-case effect).
- **A file write is reversible only if** it's Maya-owned, versioned/restorable, **and** not read by another process/app before undo. A write another process consumes → **irreversible**.
- **Open-in-app:** Maya-owned artifact for the owner → free. Opening/executing an **arbitrary or untrusted-path** file → **gated** (could be malicious).
- **Path/name control:** a local artifact can run free only when Maya chooses the workspace path/name or derives a safe slug. A path, filename, app, sheet name, tab name, or click target supplied by untrusted content remains a control value and is still governed by source-trust.
- **Memory writes:** the *action* is reversible (supersede/forget exists). But the *content* is still governed by source-trust — untrusted content cannot become owner-trusted control material. That block is the existing taint gate, **not** something reversibility frees. So: owner-authored memory write → free/reversible; untrusted-derived "remember this as fact/target" → still blocked by source-trust.
- **Calendar/local state:** add a local-only event → reversible (free). Add an event that **sends invites to others** → irreversible (gated).
- **Browser inspect/read/navigate** → reversible. **Browser click is not automatically reversible.** A click is free only when classified as link navigation/read-only/no-submit inside Maya's browser boundary. Form submit, login, purchase, booking, payment, upload, permission prompt, download/open arbitrary file, or any remote mutation → irreversible/gated.
- **Browser form fill without submit** → reversible. **Submit** → irreversible.
- **Skill/routine activation:** selecting an already-approved local skill for the current contained task may be reversible. Enabling/disabling/deleting skills, installing/scaffolding skills, creating/disabling routines, or changing future autonomous behavior remains gated unless a later locked taxonomy proves it fully contained.
- **Provider/cost risk:** reversibility does not waive spend. High-cost model/tool calls, paid APIs, or generation with external provider cost require budget policy or confirmation even if the artifact is locally undoable.

---

## Registry-grounded initial mapping constraints
These are constraints for Codex's Step 3 mapping pass; they are not implementation yet.

- `screen.capture`, `browser.inspect`: Tier R.
- `file.create`, `docx.create`, `xlsx.create`, `pptx.create`, `blender.create_model`: Tier R only when output is Maya-owned, local, undelivered, restorable, and budget/cost policy permits.
- `browser.click`: split required. Read-only navigation may be Tier R; submit/mutation/login/payment/upload/download/open-arbitrary-file remains Tier I.
- `memory.write`: Tier R only for owner-authored or Maya-process notes with correct provenance; untrusted-derived memory remains source-trust constrained and must not become owner-trusted control material.
- `skill.activate`: not blanket Tier R. Treat as gated unless the handler proves it is a current-task-only selection of an already-approved skill.
- `mcp.call`, `repo.apply_patch`, `telegram.send_file`: Tier I.
- Unknown tools or tools without a conformance row: Tier I.
- Any handler/path still unproven by Step 0b conformance remains Tier I if it has any irreversible or disclosure branch. A registry tool may only be Tier R through a path whose containment/gating is proven or whose effect is read-only and disclosure-gated.

---

## What this is honestly expected to recover (don't oversell)
Per the 2026-06-19 AgentDojo data, recoverable utility is **workspace-shaped**: drafts, reads, local artifact creation, browser reads. Travel/banking/send tasks are irreversible by nature and **stay gated** — they are *correct* refusals, not over-gating. So expect **modest, workspace-concentrated** utility recovery and a *felt* daily-use improvement, **not** a big AgentDojo-number jump. If the post-Step-3 AgentDojo utility leaps, suspect something irreversible slipped into Tier R.

---

## §6 Acceptance twins (must build all of these)
- **Must-succeed (reversible runs free, no friction):** draft a doc; read/summarize a file or email; browser-read a page; scratch-edit a Maya artifact; lookup; create an undelivered artifact. All complete without a confirmation prompt.
- **Must-fail (irreversible stays gated even on a clean owner trigger when provenance/records fail):** send email; pay; delete a file; book a hotel; post; repo push; submit a form; present-to-room.
- **THE orthogonality twin (the one that proves Step 3 didn't open a hole):** an **untrusted-triggered reversible** action completes (reversibility win) **WHILE** an untrusted value trying to set that action's control **target** is still blocked (content-vs-control intact). One test, both assertions.
- **Regression:** re-run the held-out attack slice → ASR unchanged; re-run the security harness (0.5) → no new unsafe quadrant; re-soak → no new wedge class.

---

## Lock checklist (what "locked" means for this artifact)
- [x] Reviewer + owner agree the Tier R list contains nothing observable-before-undo.
- [x] Every gray-zone ruling accepted or amended.
- [x] The orthogonality clause is understood as load-bearing (Step 3 must not touch the taint gate).
- [x] Codex's registry-grounded amendments are accepted.
- [x] Only after lock does Codex map actions onto Tier R / Tier I via the tool registry `side_effect_level`.
