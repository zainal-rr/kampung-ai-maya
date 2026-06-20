# Maya UI — LLM Council Review

Date: 2026-06-11
Method: Karpathy LLM Council pattern — Stage 1: three independent council members (agent-systems architect, product designer, reliability engineer) answered the same brief; Stage 2: anonymized peer review ranked and critiqued the answers; Stage 3: chairman synthesis below.
Research inputs: current OpenAI Codex app capabilities (threads by project, scheduled Automations, PR/diff review, worktrees, terminals, in-app browser, skills) and Claude Code capabilities (plan mode, subagents, deterministic hooks, skills, background-task notifications, persistent memory).

## Q1 — What the Maya UI needs to become the best (ranked)

1. **Live runtime mirror, not a dashboard.** Every visible state must trace back to a specific event in the append-only store. "Why is Maya doing this?" should be answerable by clicking, not by asking.
2. **Blast-radius visibility.** For any running work: what it has touched AND what it could still touch (its permission cone). If The Artisan holds filesystem write access mid-run, that must be obvious without clicking. (Top-ranked insight by peer review.)
3. **Irreversibility signaling.** Reversible draft vs confirmed action vs hard-blocked must be visually distinct everywhere — threads, artifacts, audit stream. The kernel does the work; the UI makes the weight legible.
4. **Decision-first, never dimmed.** Approvals render first, above the fold, always. Peer review explicitly rejected "aging approvals dim" — a dimmed hard-block is still a hard-block.
5. **Mid-run steering.** Pause / redirect / inject context into a running /complex loop without cancelling the checkpoint chain. Cancel-or-nothing is too coarse for a looping agent.
6. **Failure-first health.** Every surface carries its own staleness signal. A lane that produced nothing for 3 days should look different from one that ran this morning. Silently-stopped things must be visible.
7. **Trust ladder.** The UI should show Maya *earning* autonomy over time — canary health, QA history, proof scores as primary surfaces, which the design already does well.

## Q2 — Alerts? Skills place? Automation? Routines?

All four: **yes** — with specific shapes.

| Surface | Verdict | Shape |
| --- | --- | --- |
| **Alerts** | Yes, mandatory | Two tiers only. Tier 1 (interrupt): permission hard-blocks, canary trips, self-heal exhaustion, spend threshold — mirrored to Telegram so the UI is never a deaf client. Tier 2 (notify): async work completed. No FYI pings. |
| **Skills place** | Yes, right-sized | One read-mostly registry: lifecycle badges (draft→proposed→approved→active→disabled), last-run outcome, QA state, promote/disable toggle. No marketplace — one user. Reliability angle: unknown skills = unknown blast radius. |
| **Automation** | Yes, first-class | Dedicated surface: next trigger time, last outcome, permission level, audit trail, one-tap suspend, kill switch. Codex Automations made this a baseline expectation. |
| **Routines** | Yes, unified with Automation | Morning briefing / evening recap / weekly reflection are automations with a tone label, not a separate concept. Council's sharpest line: **a routine that silently stopped running is worse than one that never existed.** |

Net: the current 5 tabs grow by ONE — an **Automations** tab (or Desk section) — and skills become a visible registry (could live inside Proof or Desk).

## Q3 — Gaps vs Codex app and Claude Code (ranked)

1. **Parallel thread visibility** — both competitors show concurrent agents side by side. Maya runs parallel background workflows but the UI has no multi-run view with per-run budgets and states.
2. **Diff / change surface** — Codex shows diffs with commenting; Claude Code shows file changes. Maya shows QA verdicts but never *what actually changed* between artifact v1 and v2 or in an Artisan worktree. Need a before/after delta view, including "comment on the change" as an edit request.
3. **Schedule surface** — Codex Automations show upcoming triggers with context. Maya's routines are invisible until they fire (resolved by Q2's Automations surface).
4. **Permission-gate transparency** — Claude Code surfaces which hook fired. Maya's kernel is equivalent or stronger but the UI never shows *which gate fired and why*. Most Maya-specific gap per peer review.
5. **Run steering controls** — no pause/redirect mid-loop anywhere in the mockup (Claude Code's plan mode covers pre-execution; Maya needs in-execution too).
6. **Completion notifications to the UI client** — Claude Code notifies on background completion; Maya's UI has no notification contract of its own.
7. **Isolation visibility** — Artisan already uses isolated worktrees (Codex parity in the runtime), but the UI never shows a "running isolated · apply-back needs approval" badge.
8. **Kill-all panic button** — visible on every tab. Neither competitor has it as prominently as a single-operator system should.

**Where Maya already beats both:** memory canaries and governance, artifact QA gates with draft honesty, MYR cost ledger per lane, voice-session continuity in the same thread, proof-boundary honesty. No competitor surfaces any of these. Keep them front and center.

## Council-rejected ideas (do not build)

- Persistent cross-tab ambient status strip — duplicates Telegram's role as the remote channel; adds noise to an optional UI.
- Knowledge-graph memory navigation — canonical memory is flat event-sourced rows; graph-feel navigation before the data model supports it is premature.
- Dimming/decaying unanswered approvals — creates a false sense that inaction is safe.

## Visual Council Round 2 (2026-06-11, from rendered screenshots)

Method: mockup rendered headlessly at 1680px to 10 PNG screenshots (all 6 tabs light, guide mode, alert tray, Desk+Conversation dark). Three members (visual designer, UX designer, frontend QA) reviewed the images; chairman verified claims against the screenshots; peer review ranked and filtered.

### Accepted issues (ranked by impact)

1. Approvals not findable in under 2 seconds — buried mid-grid below the new Live-runs panel. Fix: sticky full-width approval strip at the top of Desk when approvals exist.
2. Artifacts tab badly imbalanced — gallery ends ~50% page height with dead cream space; right column nearly full. Worst spatial defect in the app.
3. Desk right column noticeably taller than left — rebalance tiles.
4. Dark mode tile contrast too low — card barely lighter than page, borders too faint; lift card surface and border opacity.
5. Dark mode secondary table text under 4.5:1 contrast — accessibility fix required.
6. Guide mode outlines everything at once — noisy; highlight only hovered element with a soft tint instead.
7. Desk tiles all equal visual weight — introduce two tiers (primary: live runs/approvals; secondary: compact/collapsible).
8. Route/cost table rows look clickable but are not — add chevrons (if drill-down) or flatten styling.

Also accepted (lower impact): gold accent overused (reserve for approval/pending), proof bars need a threshold marker (e.g., 80% line) and health coloring, alert tray tiers need color-coded left borders, teach-Maya input reads as a search field (make it a labeled textarea), file tree needs folder/leaf affordances and wider min-width, guide tooltip needs a pointing caret, file-type badges could carry distinct low-saturation hues.

### Rejected by chairman verification

Proof-tab whitespace gap (already fixed), "red deletions" in the diff (none exist), "forgotten badge unstyled" (it is styled), toggle size misjudged (34x20, fine), hallucinated labels ("Memory Salaries", "Subconscious Proof") — misreads of small rendered text.

### Render caveat

Webfonts (Satoshi/JetBrains Mono) did not load in the sandbox render; typography critiques were partially based on fallback fonts. Re-verify type rhythm in a real browser.

### Council-praised (keep as is)

QA verdict panel (clearest information design in the app), Automations rows (status + toggle ergonomics), the diff "What changed" panel, nav strip, logo + greeting header, dark theme's accent calibration.

## Visual Council Round 3 (2026-06-11, post-fix screenshots)

Both members scored the design **7.5/10 — "strong foundation, close to lock."** All ten round-2 fixes verified as resolved (dark contrast judged "partial" in deepest secondary text).

### Accepted new issues (chairman-verified)

1. **Approval redundancy (pattern-level, must fix before lock):** the sticky strip AND the Approvals tile both carry action buttons for the same items. Fix: strip becomes the sole action surface; the tile becomes read-only status ("2 pending — resolve above or in chat").
2. **Proof tab lacks a hero anchor:** no single confidence signal on first glance. Fix: render the overall score (85%) as a large display numeral above the bars.
3. **Proof bar color semantics:** formalize green ≥85 / gold 70–85 / rose <70 so triage is pre-attentive (two bars already gold; make the rule explicit).
4. **Gate-decision badges read as actionable:** state chips (allow/confirm/deny) look like buttons. Fix: add "read-only · decisions resolve in chat" hint to honor "chat to act, UI to see".
5. **Conversation context pane density:** six QA rows visible at once; collapse to one "QA: pass" badge, expand on demand.
6. **Gate decisions sits at the bottom of Desk left column:** swap above The Team tile for more authority.
7. Minor: teach textarea border too faint in light mode; alert tray could use per-item dismiss ghost affordance; dark-mode deepest secondary text could lift one more step; dark user-bubble contrast needs an in-browser check (render too small to judge).

### Rejected (chairman verification)

"Gate decisions has inline approve/reject toggle buttons" (rows have badges, no buttons — reframed as issue 4), "all toggles look the same regardless of state" (off-state IS grey; all six shown are genuinely on), "every proof bar same olive" (agentic + hardware are already gold), hallucinated labels ("The Tome", "The Seer/Arbiter/Witness", "Staff meal — vacation budget") — small-text misreads.

## Sources

- Karpathy LLM Council pattern: github.com/karpathy/llm-council
- Codex app: openai.com/index/introducing-the-codex-app, developers.openai.com/codex/changelog
- Claude Code: code.claude.com/docs (hooks), community capability guides (2026)
