# Maya Meet — Feature Plan (Conversation Hold + Presenting)
*Reference doc. 2026-06-19. Scope: make Maya feel like a natural participant in a meeting Zainal hosts. Deliberately lean — this is engagement/UX convenience, not new security surface. The authority and disclosure gates already built are untouched.*

## The one principle (stated once, not belabored)
A conversation hold changes **engagement** (does Maya keep answering), never **authority** (what she can do). "Maya, send the file" still routes to Telegram phone confirmation, exactly as today. False engagement is at worst awkward, never harmful — which is why this is safe to keep simple.

Threat reality for this feature: it's Zainal's meeting, his invitees, he's present, and any real action needs his phone. The realistic hijack risk through a conversation hold is ~nil. Build it simply.

---

## Feature 1 — Conversation Hold (continuous conversation)
Today: every utterance needs "Maya, …". Goal: once addressed, she stays in conversation until told to stop.

**Behavior:**
- **Open:** Zainal says "Maya, …" → she answers AND the hold opens.
- **Attentive:** she keeps responding to what's said next **without needing her name** — a normal back-and-forth.
- **Close (any of these):**
  - Close phrase: "thank you Maya", "that's all Maya", "okay Maya thanks" (small variant list).
  - Idle timeout: no one addresses her for a generous window (e.g. ~3 min) → she drops the hold. (This is a "don't leave the mic hot after everyone leaves" convenience, not a security guard.)
  - A different person opens their own hold by saying "Maya" → focus moves (one active hold at a time).
  - The meeting/bot ends.
- **Echo-aware:** Maya's own Output Media speech must not count as activity that keeps the hold alive — reuse the existing echo filter.

**Deliberately NOT in v1 (don't over-engineer):**
- No speaker-binding diarization.
- No "is this directed at me vs a side conversation" intent disambiguation.
- If she occasionally answers something not meant for her, you say "thank you Maya" and move on. Accepted tradeoff.

**Unchanged (do not touch):**
- Authority: room speech is still `other_speaker`; high-risk/effectful actions still need owner phone confirmation.
- Disclosure: owner-private data still can't be recited to the room on a non-owner request.

---

## Feature 2 — Screen share / presenting (clarification + optional capability)
- **Zainal sharing his own screen:** native Google Meet feature. Always works. Maya does not gate, touch, or interfere. Out of scope — it just works.
- **Maya presenting INTO the room (optional, Recall Output Media):** "Maya, show them the deck" → Maya pushes a document/webpage into the meeting as shared content.
  - Ties into the desktop flow: create docx/xlsx/pptx → open it → (optional) present it to the room.
  - This is the one "show on screen" that is *Maya* disclosing to the room, so it's a disclosure action: on Zainal's own request, showing Zainal's own content → fine. The existing disclosure gate already covers the edge case (don't let a non-owner make Maya present owner-private content to the room).
  - Mark as a follow-on item; the conversation hold (Feature 1) is the priority.

---

## Feature 2a — Document → presentable HTML (the present-into-room flow)
When Maya presents a document into the room, she renders it to a **static HTML page** first — HTML is Output Media's native format (Word → clean HTML, Excel → table, PPTX → slide sections), so doc → HTML is the standard conversion, not a workaround. Three hands, kept separate so no lane grades its own homework:

1. **Steward designs the frame (taste skills).** The reviewer lane produces the design spec — layout, typography, slide structure, how a table/quote should look. **Content-agnostic:** it designs the *template*, not the content, so it never needs the raw (possibly untrusted) doc values. The design spec is *content* (a suggestion about look), never authority — it cannot decide what gets presented.
2. **Worker builds it.** Artisan/Codex fills the Steward's template with the doc content and applies the **static-sanitize rule**: strip scripts, no remote loads, inline-only. Untrusted content stays inert display, never active markup (content-vs-control applied to rendering). The HTML is a reversible Desktop artifact → free.
3. **Deterministic gates clear the present.** The two impartial checks are code/kernel, **not** a lane's opinion — so the Steward having shaped the look does not self-grade:
   - *Inertness* — deterministic sanitizer in the build step (no active markup got through).
   - *Disclosure* — the disclosure gate + owner phone. Only edge that bites: owner-private content heading to a non-owner room. Your own content on your own request → fine.

Net: the lane that shapes the look (Steward, taste) ≠ the lane that builds (Worker) ≠ the thing that authorizes the present (deterministic gates). Same spine as everything else.

*Fidelity caveat:* PPTX → HTML is a *view* of the deck, not pixel-perfect. Fine for display-only.

---

## Desktop ↔ Meet bridge (context, already settled)
Reversible/contained, run freely (no friction), consistent with how Zainal uses the iMac:
- `create_docx` / `create_xlsx` / `create_pptx` on Maya Desktop → free.
- `open_document` / launch-in-local-app to view → free.
- browser navigate / read → free.
- Gate only ever appears at the genuinely external/irreversible step (send out, submit/post, pay, destructive delete) — and presenting to the room is disclosure-gated only for owner-private content on a non-owner request.

---

## Test twins (light — prove it works, prove it can't act)
- **Must-engage:** address Maya mid-hold without her name → she responds.
- **Must-close:** say "thank you Maya" → she stops responding; idle past the window → hold drops.
- **Must-not-act:** "Maya, delete the file" mid-hold → she engages but the action still routes to phone confirmation (authority unchanged).
- **Echo:** Maya's own spoken output does not keep the hold alive or trigger a response loop.

---

## Discipline
Same as everything else: write spec → review → build on a branch → **live-test on a real Google Meet** (the conversation hold is a UX behavior; it's only proven when it feels right live), then commit. This is a Meet-lane (M-series) feature, separate from the security/memory roadmap.
