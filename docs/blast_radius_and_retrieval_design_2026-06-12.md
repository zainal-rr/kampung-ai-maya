# Blast-Radius Control (W5) + Retrieval (W2) — Design (2026-06-12)

Status: **STAGE 1 BUILT 2026-06-12** (W5-1 path jail + Artisan env scrub; W2-A
supersede). W5-2 OS-enforcement and W2-B semantic recall remain Phase-7-informed
(unbuilt, by design). Canaries specified first (same discipline as the context
window). Verified against the tree before writing — the load-bearing claims
below were checked, not assumed.

## Stage 1 build record (2026-06-12)

- **W5-1 path jail:** `safe_paths.py` — `resolve_safe_path(path, mode)`
  chokepoint (allowlist roots + hard denylist that overrides, fail-closed) and
  `scrubbed_subprocess_env()`. Wired into `file_actions.py` (write),
  `document_actions.py` (`_path` output), `telegram_delivery.py`
  (`_allowed_file_marker`, so a credential file can't ride a `[file:]` marker
  out), and `artisan_runner_engine.py` (Codex child runs with scrubbed env).
- **W2-A supersede:** `canonical_memory_supersede.py` + `canonical_memory.py` —
  partial unique index on active rows, prior value archived as `superseded`
  before in-place update, `canonical_memory_history()` for "what was it before",
  forget covers the whole chain. New audit event `canonical_supersede`.
- **Canaries (red-first, now green):** `tests/smokes/blast_radius_canaries_smoke.py`
  (S1-S7), `tests/smokes/memory_supersede_canaries_smoke.py` (R1-R3). Both
  wired into `local_ci.py`.
- **Verified:** code_health 0 violations (canonical_memory.py refactored to 294
  lines), memory recall regression (multi-fact recall + relevance + selective
  forget) green on the new schema. NOTE: full `canonical_memory_smoke.py` and
  `local_ci.py` must be run on the iMac (Python 3.11+; this sandbox is 3.10 and
  several pre-existing modules import `datetime.UTC`).

Scope: the two council weaknesses that matter for a PERSONAL (single-user)
Maya. W5 = limit what happens when an intent gate is wrong (blast radius).
W2 = make Maya actually recall what it stored (the most visible daily failure).
The other two council items (W3/W4-class) are product-scale and out of scope.

## Verified facts (checked 2026-06-12, not assumed)

1. **The planner's reachable tool surface is narrow.** `maya_tool_registry.py`
   exposes 13 tools. The only path/process-capable ones: `file.create`
   (write), `docx.create` / `xlsx.create` / `pptx.create` (write w/ output
   path), `blender.create_model`, and `mcp.call` (permission_scope
   `run_command`). There is NO general shell tool and NO arbitrary
   `file.read` in the planner surface; reads are `screen.capture` and
   `browser.inspect` (visible content, not the filesystem).
2. **CORRECTION — the bash-like capability already exists: Artisan.** The
   Artisan/Codex lane executes generated code with the full user account:
   `artisan_runner_engine.py:46` (`asyncio.create_subprocess_exec`),
   `artisan_apply.py` + `artisan_worktree.py` (git against the tree). It is
   approval-gated, but it executes arbitrary generated code, so the W5-1
   credential-read canary is FALSIFIABLE TODAY via "ask Artisan to write a
   script that reads ~/.ssh". Therefore Artisan's runner is in W5-1 scope,
   not deferred to a later tier.
3. **Embedding rerank infra already exists.** `canonical_memory_embeddings.py`
   has `RERANK_CONFIDENCE = 20` (line 16), used as a threshold at line 57. The
   W2 semantic-fallback amendment lands on existing machinery.

## Principles (carried from the rest of the system)

- Deterministic gate where the guarantee matters; one chokepoint, fail-closed.
- Verify-before-scoring: claims are checked against the tree.
- Eval-first for capability bets: don't build the heavy version blind when
  Phase 7 will name the real failures.
- State the limit honestly, in the doc, the way W7 records "regex is
  bypassable" — so future-you never mistakes a policy for a guarantee.

---

# W5 — Blast-Radius Control

Threat model: an injection slips BOTH the regex detector AND the W7 influence
gate (the docs already admit regex is bypassable). Today, the action then runs
with the full user account. Defense in depth: even when the intent gate is
wrong, contain what can happen.

## W5-0 — Capability audit (do first, cheap)

Enumerate every path-taking and process-spawning capability reachable by (a)
the planner/harness and (b) the broader Maya process — the same method as the
W7 read-surface audit (`untrusted_read_surface_audit_2026-06-11.md`). Output:
the authoritative list the jail must cover. The narrow planner surface is
already known (above); the audit's job is to confirm nothing else reaches the
filesystem unguarded, and to place Artisan explicitly in scope.

## W5-1 — Filesystem path jail (the real fix, build-now)

One deterministic `resolve_safe_path(path, mode)` chokepoint every path-taking
tool routes through. Fail-closed on anything unresolvable.

- **Writes:** allowlist to workspace roots only (Desktop/Maya, configured
  project dirs, scratch). Covers `file.create` and the three document
  creators.
- **Reads:** allow workspace + a small set of common doc locations; a HARD
  DENYLIST overrides even an allowlisted path — `~/.ssh`, `~/.aws`,
  `~/.config/gcloud`, `*.pem`/`*.key`, `.env`, login keychains, browser
  profile dirs, the secret store.
- **Artisan in scope (the correction):** Artisan's runner gets env scrubbing
  (no credential env vars in the child process) and write-confinement to its
  worktree. The generated code still runs, but it runs without the
  credentials and outside the rest of the disk.

Honest limit (Amendment 2, written here on purpose): **`resolve_safe_path()`
is in-process policy, NOT OS containment.** A Python-level check does not bind
a child process that decides to ignore it. This is an acceptable trade TODAY
given the narrow surface + per-call confirms, but if `run_command`/MCP/Artisan
usage grows, OS-level enforcement (sandbox-exec / restricted user / container)
becomes the next tier. The jail is a policy, not a sandbox — do not confuse them.

## W5-2 — `mcp.call` / `run_command` + OS enforcement (Stage 2 built 2026-06-17)

`mcp.call` with `run_command` scope is the open-ended wildcard: an MCP
connector can do anything. Already external-gated, but "approved once" should
not mean "unbounded." Stage 2 adds an execution broker for command-like child
processes: allowlist environment inheritance, restricted PATH, timeouts,
optional network, swappable macOS `sandbox-exec` enforcement, and explicit
audit-friendly profiles. `sandbox-exec` is deprecated by Apple but still
available on the iMac; the broker is the abstraction so this backend can be
replaced later.

W5-2 does **not** claim OS containment for logged-in Chrome, Office, launchd,
or other GUI/service integrations. Those paths remain governed by strict
extension mode, W7 provenance, verified facts, explicit service commands, and
no-silent-fallback rules. Browser/GUI is governed, not sandboxed.

Honest W5-2 limit: `read_roots` currently drives credential-deny discovery,
not a full read jail. The broker denies credential-shaped paths, constrains
writes to safe roots, strips child environments, blocks network unless a
profile asks for it, and kills timed-out process groups. A stricter general
file-read jail remains a later hardening tier because broad read access is
still needed by several macOS/CLI tools.

## W5 canaries (written FIRST, failing, before code)

| # | Canary | Asserts |
| --- | --- | --- |
| S1 | Credential read denied | `resolve_safe_path("~/.ssh/id_rsa", read)` → denied, even with an explicit instruction in the request. |
| S2 | Out-of-jail write denied | Any write outside the workspace allowlist → denied; in-workspace write → allowed. |
| S3 | Denylist overrides allowlist | A credential path that happens to sit under an allowed root is still denied. |
| S4 | Artisan credential read denied | An Artisan task instructed to read a credential path cannot — env scrubbed + worktree-confined (the falsifiable-today case, now closed). |
| S5 | Chokepoint exclusivity | No path-taking tool reaches the filesystem without `resolve_safe_path()` (repo grep + call-graph, like context-window C3). |
| S6 | Fail-closed unknown | An unresolvable/symlink-escape path → denied, not allowed. |
| S7 | Honest-limit acknowledgement | A test/doc assertion that the jail is in-process policy (S-series does not claim OS containment) — prevents future over-trust. |

---

# W2 — Retrieval

Memory governance (Phase 3) protects truth; retrieval is whether Maya USES it.
Failed recall is the most visible personal-assistant failure — the moment Maya
feels like it doesn't know you.

## W2-A — Supersede instead of overwrite (deterministic honesty fix, build-now)

Problem: "my rent was X, now it's Y" overwrites and silently loses history.

Fix: on a changed fact, do not overwrite. Mark the prior canonical item
`superseded` (a NEW status, distinct from `forgotten`) with a validity
interval; the new value becomes active. Retrieval returns the current value by
default and can surface history on demand ("currently Y; was X before
[date]"). Same family as the forget watermark: deterministic, no model
dependency, and it's a memory-HONESTY improvement (stops silent history loss).

Interaction with forget: `superseded` and `forgotten` are different terminal
states; a forget still tombstones across all tiers (Phase 3 + context-window
watermark). Supersede keeps history retrievable; forget removes it.

## W2-B — Paraphrase recall via confidence-triggered semantic fallback (build-AFTER Phase 7)

Problem: lexical retrieval (`memory_tokens` overlap) misses paraphrase —
store "favorite airline is AirAsia", ask "which carrier do I prefer?" → miss.

Fix shape (hybrid, NOT rip-and-replace): keep lexical as the primary path
(fast, explainable, it is the honesty story). Add an embedding fallback —
but per Amendment 1, **trigger on WEAK LEXICAL CONFIDENCE, not on empty
results.** The common failure is lexical returning something weakly-related and
wrong, so an "only when nothing returns" trigger would never fire. Use the
existing `RERANK_CONFIDENCE` threshold pattern in
`canonical_memory_embeddings.py`. Guard: vector-only evidence may not WIN a
direct-recall question — semantic can surface a candidate, lexical/exact still
arbitrates, so a related-but-wrong memory cannot impersonate a direct hit.

Why AFTER Phase 7: the eval already shows weak paraphrase recall, but WHICH
paraphrases fail in real use is exactly what Day 2's `[MEMORY]` pile names.
Building embeddings blind risks semantic false positives — retrieving
related-but-wrong, which for memory is worse than a clean miss. Field data aims
the fix.

## W2 canaries

| # | Canary | Asserts |
| --- | --- | --- |
| R1 | Supersede keeps history | Update a fact → old value `superseded` not gone; current returns new; history query returns both with dates. |
| R2 | Supersede ≠ forget | A `superseded` item is still retrievable as history; a `forgotten` item is not (Phase 3 intact). |
| R3 | Forget over supersede | Forgetting a fact that has a supersede chain removes the WHOLE chain (no resurrect via history). |
| R4 | Paraphrase recall (W2-B) | "which carrier do I prefer?" retrieves the stored airline fact via the confidence-triggered fallback. |
| R5 | No vector false-win (W2-B) | A weakly-related vector hit does NOT override an exact lexical answer on a direct-recall question. |

---

## Staging (guarantees ahead of capability)

1. **Now, parallel (deterministic, no field data needed):**
   - W5-0 audit → W5-1 path jail (incl. Artisan env-scrub + worktree confine).
   - W2-A supersede.
   - Canaries S1–S7, R1–R3 written first.
2. **Phase 7 runs** (window + loop validated in real use; `[MEMORY]` pile
   collected).
3. **After Phase 7, field-informed:**
   - W5-2 `run_command`/MCP tightening; OS-level enforcement IF volume warrants.
   - W2-B confidence-triggered semantic fallback; canaries R4–R5.

## Honest limits (recorded, not hidden)

- W5-1 is in-process policy, not OS containment (Amendment 2). It binds Maya's
  own tool calls and Artisan's scrubbed child env; it does not bind a
  determined child process. OS enforcement is W5-2's job if the surface grows.
- The path jail does NOT solve browser authority: Maya drives the real
  logged-in Chrome, so "use my session" is contained by W7 + kernel confirm
  gates on browser ACTIONS, not by a filesystem jail. Separate problem,
  separate owner.
- W2-B can introduce semantic false positives; the confidence trigger +
  no-vector-false-win guard bound it, but the honest failure mode is
  "surfaced a related-but-wrong candidate" — which is why lexical stays
  primary and arbitrates.
