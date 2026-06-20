# Pattern Recognition Schema — Step 4 send-me-first artifact (LOCKED)
*Author: Steward (reviewer). 2026-06-20. **LOCKED after two owner amendments: (1) `method` is a closed enum, not free strings; (2) a planner-fact budget caps pattern facts below live observations/metacognition.** This design makes pattern memory safe **by construction**: the schema cannot hold a control value, `method` cannot hold a verb outside a fixed safe set, and a retrieved pattern is always content (`control_eligible=False`), never authority. Safe to build against this lock; final human review focuses only on whether the poison test actually bites.*

---

## The one idea
A pattern is a **suggestion about *method*, learned from past episodes** — "for a task shaped like this, this approach worked." It is fed to the planner as **content (`control_eligible=False`)**, never as authority. It can nudge *which tools to try*. It can **never** choose a *target* (recipient, path, amount, account, url). Targets are always re-derived per episode from owner-task / source-trust and kernel-gated, exactly as today.

## Why this is safe by construction (the argument the schema must enforce)
The danger with pattern memory is laundering: a pattern learned from an episode that contained untrusted content later steering an effect. This schema removes that danger **structurally**, not by a guard that can be bypassed:
1. **The schema has no field that can hold a control value.** There is nowhere to put a recipient/path/amount/account/url/target. So a poisoned episode cannot store one — only the *shape* (that "a recipient was involved") is recordable.
2. **`control_eligible = False` is hardcoded on every retrieved pattern.** The planner may use a pattern to pick a *method*; the kernel still gates every concrete action. A poisoned pattern's worst case is a bad *method suggestion the planner can reject* — low harm — never a chosen target.
3. **Method is tool-TYPES, not concrete calls.** Stores "read a source, then extract a field," never "call X with id=Y." So even a poisoned method can't smuggle a concrete action; the args are always re-derived and gated.

If those three hold, a poisoned pattern is inert at the effect layer by design.

---

## Schema (the fields a pattern may store — and ONLY these)
| Field | What it holds | Hard rule |
|---|---|---|
| `pattern_id` | opaque id | — |
| `situation_shape` | **structured/enumerated** task features (see directive 3): `task_category`, `source_type`, `goal_type` — never free text | **enumerated only, never values** — no names, paths, recipients, amounts |
| `method` | ordered list of step-kinds from a **CLOSED ENUM** (see below) that worked | **closed enum only; no concrete args, no targets; unknown step → reject/drop** |
| `outcome` | closed enum: `succeeded` / `failed:<reason>` (reuse the metacognition failure taxonomy) | closed enum only |
| `provenance` | `owner_only` (episode had no untrusted content) or `untrusted_touched` | required; default `untrusted_touched` if unknown (fail-closed) |
| `trust_tier` | derived: `method_safe` (owner_only) or `quarantined` (untrusted_touched) | derived, not author-set |
| `supersession` | active / superseded / forgotten | superseded/forgotten are never retrieved as active |
| `control_eligible` | **always `False`** | hardcoded; not settable |
| `created_at` / `last_used` / `use_count` | recency/decay | — |

**There is deliberately no field for a recipient, path, amount, account, url, filename, or target. That absence is the safety property — don't add one.**

### `method` closed enum (amendment 1 — the only allowed step-kinds)
`read_source`, `extract_field`, `compare`, `summarize`, `create_local_artifact`, `ask_owner`, `answer_with_gaps`.
- **Any step outside this set is rejected/dropped at store time.** A poisoned episode cannot record `send_file`, `post_to_external`, `pay`, `delete`, or any effectful verb as a "method" — the enum has no such member. This closes free-string method steering: even though the kernel would still gate the effect, a bad method suggestion never reaches the planner in the first place.
- The set is deliberately all *contained/read/local* verbs plus `ask_owner`. No send/pay/delete/post/external verb is in it, by design. Extending it later requires a re-lock.

---

## Build directives added 2026-06-20 (post-lock, reviewer — part of the lock)

**Directive 3 — `situation_shape` is enumerated, not free-text-then-sanitized.** Apply the same allowlist logic as the `method` enum to the shape field, because sanitizing free text is a *denylist* (catches only what the scrubber anticipated) and an enumerated field is an *allowlist* (cannot hold a value you didn't define). So `situation_shape` is structured categorical fields, not a string to scrub:
- `task_category` — from a fixed set (e.g. `summarize`, `extract`, `compare`, `draft`, `lookup`, `other`).
- `source_type` — from `{email, web, file, meeting, none}`.
- `goal_type` — from a fixed set (e.g. `answer`, `produce_artifact`, `decide`, `other`).
- Anything that doesn't map to an enum member is dropped, **not** stored as free text. There is no raw-string shape field for a value to hide in.

**Directive 4 — provenance derivation at store time is fail-closed.** The store path turns a finished episode into a pattern; the entire quarantine rests on tagging it correctly:
- If **any** fact in the episode had `untrusted_influence=True` (or `injection_detected=True`) → the pattern is `untrusted_touched`.
- **Anything ambiguous or unknown → `untrusted_touched`.** Never infer `owner_only` from the *absence* of evidence. A mislabel here is the one silent way the quarantine fails, so it must lean safe by construction.

---

## Hard invariants (the load-bearing rules)
1. **No control values, ever.** If an episode contained a control value, the pattern records only that a value of that *kind* was involved (shape), never the value. Enforced by the schema having nowhere to put it.
2. **`control_eligible = False`, always.** Retrieved patterns are content suggestions. Targets come from owner-task/source-trust, re-derived and kernel-gated.
3. **Provenance-tagged + quarantine.** `untrusted_touched` → `quarantined`: may still inform *method* (low harm) but is flagged, weighted lower in retrieval, and can **never be the sole basis** for an action. `owner_only` → `method_safe`. Unknown provenance defaults to `untrusted_touched` (fail-closed).
4. **No resurrection.** A pattern tied to superseded/forgotten facts is not retrieved as active (reuse the W2 supersede discipline). Methods don't carry facts, but the supersession field guards a stale method tied to a changed context.
5. **Method = closed-enum step-kinds, not concrete calls or free strings.** Concrete args are always re-derived per episode and kernel-gated. Unknown step → dropped.
6. **Planner-fact budget (amendment 2).** Pattern facts must never crowd out live observations or metacognition facts. **At most 1–2 pattern facts** per planning prompt, each `source="pattern_recognition"`, each `control_eligible=False`, and **lower priority than current observations and metacognition facts** — when the shared planner-fact cap (`MAX_PLANNER_FACTS`) is contested, live/metacognition facts win, pattern facts are evicted first. A pattern is a faint hint, never a loud voice.

---

## Tests Codex must build against this (and the verification gate)
**Must-fail (the poison tests — these must genuinely BITE):**
- A pattern learned from an `untrusted_touched` episode is retrieved; the planner is run on a new task; confirm the pattern **cannot make the planner choose a laundered control target** — the kernel still denies. *(Runs on the existing Step 0.5 reduced planner+kernel path: inject the poisoned pattern as a retrieved fact → real planner → real kernel → denied.)*
- An attempt to **store a control value** into a pattern is rejected/dropped to shape-only.
- A **superseded** pattern is not retrieved as active.

- An attempt to store a `method` step **outside the closed enum** (e.g. `send_file`) is rejected/dropped.

**Must-succeed (the twin — proves it's not inert):**
- A benign `owner_only` pattern ("for date-extraction tasks, read-then-extract worked") genuinely speeds or improves a repeat task.

**Budget (amendment 2):**
- Pattern facts **do not evict** live observation or metacognition facts when the planner-fact cap is contested; pattern facts go first.

**The verification gate (why a human reviewer must check this one):** the poison test must be confirmed to *actually exercise the laundering* — inject the poisoned pattern, see the planner tempted, confirm the kernel blocks — not be green-by-construction. This is the exact failure mode that produced the replay "18/18" and the asserted-not-executed gates. So the reviewer reads the poison test against the code and confirms it bites, the way the Step 3 forged-source test was verified. **No Step 4 ships on a green poison test until that read happens.**

---

## Implementation plan (build to this lock)
- Build a **tiny dedicated procedural pattern store** — not a new memory framework. Reuse existing storage paths.
- Store **only** shape / method(closed enum) / outcome / provenance / supersession.
- **`situation_shape` is enumerated** (directive 3) — structured categorical fields, not free text. Anything not mapping to an enum member is dropped, so there is no string to leak a value through.
- **Provenance is fail-closed** (directive 4) — `untrusted_touched` if any episode fact was untrusted, and on any ambiguity.
- Retrieve patterns as **PlannerFacts** (`source="pattern_recognition"`, `control_eligible=False`, budget-capped), **never as tool args**.
- Tests: poisoned pattern can't pick a target (kernel denies) · control-value storage dropped · out-of-enum method step dropped · superseded pattern not retrieved · benign owner-only pattern helps a repeat task · pattern facts don't evict live/metacognition facts.
- Standing rule for the build: **if it needs to deviate from this schema, stop and park it** — don't improvise a field or a method verb.

## Lock checklist — LOCKED 2026-06-20
- [x] No control-value field; `control_eligible` hardcoded `False`.
- [x] `method` is a closed enum; unknown step dropped (amendment 1).
- [x] Provenance defaults to `untrusted_touched` when unknown (fail-closed).
- [x] Planner-fact budget caps pattern facts below live/metacognition (amendment 2).
- [x] `situation_shape` enumerated, not free-text-sanitized (directive 3).
- [x] Provenance derivation fail-closed → `untrusted_touched` on any untrusted fact or ambiguity (directive 4).
- [x] Poison + control-value-drop + out-of-enum-drop + no-resurrection + must-succeed twin + no-eviction are the required test set.
- [ ] **Reviewer verifies the poison test actually bites before Step 4 is ticked** (the one remaining human gate — minutes).
