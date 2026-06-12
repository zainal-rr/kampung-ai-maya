# Maya / Kampung AI — Weakness Status & Next Steps (current)

Date: 2026-06-11 (latest status file; updated 2026-06-12)
Supersedes: `MAYA_REMEDIATION_NEXT_STEPS.md` (priority plan) and the two council
reviews. Use THIS file as the live status for the next session.
Method: Karpathy LLM Council (four role-seats deliberate, Chairman synthesizes),
applied as a review discipline. Public model: **self-host-per-user** (decided).

> 2026-06-11 remediation update: W1 remains fail-closed; W7 is now live-wired
> into browser page text, Chrome extension page inspection, screen summaries,
> active-context extraction, harness observations, LangGraph tool checks, and
> SDK tool calls. W3 has a typed runtime config layer for the main personal
> runtime constants. W5 has an env/keychain/auto secret provider with env still
> the default. W6 now treats the Chrome extension as the normal strict browser
> path; AppleScript is explicit `legacy` mode.
>
> 2026-06-12 update: W2 supersede-not-overwrite is implemented and CI-protected.
> The partial-index regression where repeated canary seeding collided with a
> forgotten/expired deterministic `memory_id` is fixed. W4 now has a root-file
> count guard in `code_health.py`: the current 724 top-level `.py` files are the
> ceiling, so future root growth fails CI until code moves into packages.

## Verification log (2026-06-11, independent code read — corrections folded in)

This pass re-checked every item against the actual tree, not prior docs. Where
the earlier draft was stale, it is corrected below and in the per-weakness sections.

| Item | Method | Result |
| --- | --- | --- |
| W1 verifier | read `harness_llm_planner.verify_goal` + graph | ✅ fail-closed, goal-success only on explicit verifier approval |
| W2 neighbor boost | `grep expand_with_neighbors canonical_memory.py` | **LIVE** — called at `canonical_memory.py:312` (was wrongly listed "built, not flipped") |
| W2 embedding rerank | ran baseline + `MEMORY_EMBED_RERANK_LIVE=1` evals | still env-gated; eval showed no improvement, so default stays off |
| W3 personal wiring | read + patched device/audio/workspace/browser/Telegram paths | typed `maya_runtime_config.py` now owns main runtime constants |
| W4 file count | `find . -maxdepth 1 -name '*.py' \| wc -l` | **724** top-level — root growth is now CI-guarded, but W4 remains open until package restructuring |
| W5 credentials | added `secret_provider.py` + smoke + throwaway Keychain lookup | env/keychain/auto provider exists; live Keychain read/write works; real secret migration still open |
| W6 driver | patched `browser_driver.py` + smoke | extension is strict normal path; AppleScript only via `MAYA_BROWSER_DRIVER=legacy` |
| W7 entry-tagging | patched live carriers + smoke | **LIVE-WIRED** — browser/screen/document observations carry untrusted flags into permission checks |
| W8 isolation | self-host-per-user decision | dissolves multi-tenant risk |

---

## Council deliberation (current state)

- **Architect:** W7 now has both halves: source assessment at browser/screen/
  document entry and enforcement at the permission kernel. The boundary still
  relies on conservative source-tainting more than regex perfection, which is
  the correct design.
- **Planner:** W1 is guarded, W7 has live-path smoke coverage, W3 is centralized
  enough for the main runtime constants, W5 has a transition provider, and W6 no
  longer silently falls back to AppleScript.
- **Contrarian:** W7 is not "prompt-injection proof." Regex can miss clever
  wording. The real protection is that untrusted influence gates or denies
  external/scope-widening side effects. Future live surfaces must carry the same
  flags or they reopen the gap.
- **Chairman:** The highest-risk safety boundary is now materially live for the
  current self-hosted product. Remaining work is live evidence, broader surface
  audit, Keychain migration, memory/entity quality, and eventual repo structure.

---

## How to read this doc (avoid the two easy misreadings)

1. **"Built/wired" ≠ "forever solved."** A module that passes its smoke proves the
   gate works for the surfaces under test. W7 is now wired for the current
   browser/screen/document/active-context/harness paths, but every future read
   surface must carry the same untrusted flags or it reopens the gap.
2. **Several weaknesses are really TWO problems — a "driver/mechanism" half and a
   "surface/risk" half — and they get closed by different tickets.** W6 is the
   clearest case: the driver is solved by the extension-bridge choice, but the
   browser's *injection risk* is closed under W7+W5, not W6. Read each weakness
   for which half is done and which half just moved somewhere else.

## All eight weaknesses — current status, one by one

| # | Weakness | Was | Now | State |
| --- | --- | :---: | :---: | --- |
| **W1** | Agentic loop / verifier | 4 | **3** | **Verifier CLOSED** (fail-closed, live). Loop-depth remainder = capability, not danger |
| **W2** | Lexical memory | 3 | **2-3** | **Partly wired:** neighbor/association boost is LIVE; supersede-not-overwrite is built and regression-tested. Embedding rerank remains env-gated/off because eval showed no improvement. Remaining = better recall eval/data |
| **W3** | Single-user wiring | 5 | **1-2** | Typed runtime config now owns the main personal/runtime constants. Some historical/test literals remain, but runtime behavior is centralized |
| **W4** | Flat **724**-file root | 4 | **4** | Open, now CI-guarded against more root growth. Gating item for public + bus-factor risk |
| **W5** | Credentials / sandbox | 5 | **4** | Keychain provider exists, env remains default; actual live migration + sandbox still open |
| **W6** | Browser (driver + surface) | 4 | **2** | Extension is now the strict normal path and passed the clean extension reliability run. AppleScript exists only as explicit `legacy`; removal is optional cleanup, not a proof blocker |
| **W7** | Untrusted-input boundary | 5 | **1-2** | Live-wired for browser/screen/document/active-context/harness paths; needs continued smoke/live coverage for new surfaces |
| **W8** | Multi-tenant isolation | 5 | **1** | **Dissolved** by self-host-per-user. No work unless hosted service |

### W1 — Agentic loop / verifier — verifier CLOSED
`verify_goal` only returns True on explicit YES; error/ambiguity → one reflective
retry → False (safe because `MAX_STEPS` bounds the loop). The silent-success
safety defect is gone. Remaining (capability, not safety): native function-calling,
all registry tools reachable by the planner, deeper budget. **Sev 3.**

### W2 — Lexical memory — PARTLY WIRED (not "unwired")
Correction after independent verification: this is two mechanisms at different
states, not one open item.
- **Neighbor / association boost: LIVE.** `expand_with_neighbors` is imported and
  called inside canonical search (`canonical_memory.py:312`), so 1-hop spreading
  activation already influences recall. This half is done.
- **Embedding rerank: still env-gated**, not default (`MEMORY_EMBED_RERANK_LIVE`).
  Baseline eval and `MEMORY_EMBED_RERANK_LIVE=1` eval on 2026-06-11 produced
  identical recall, so the evidence-based default decision is **keep it off**.
  The eval still shows paraphrase recall is weak; the next W2 improvement needs
  better examples, a stronger rerank candidate set, or supersede/entity work.
- **Supersede-not-overwrite: LIVE.** Changed active values are archived as
  `superseded`, current recall returns only the newest active value, history is
  available on request, and forget tombstones the whole chain. The 2026-06-12
  regression fix reactivates forgotten/expired base rows in place for explicit
  user re-saves, avoiding deterministic `memory_id` collisions.
- **Temporal validity windows: still deferred.** Supersede history exists, but
  dated validity semantics are not yet a full temporal reasoning layer.
- **Entity graph: deferred** until real scale (correct to defer).

So W2's accurate state is "partly wired, needs rerank eval/default + supersede,"
not "cheap fixes built but unflipped." **Sev 2-3.**

### W3 — Single-user wiring — typed config layer added
Self-host-per-user removed the need for an isolation layer. Remaining work:
keep migrating any new runtime constants into `maya_runtime_config.py`.
Implemented now: owner name, Telegram allowlist, Desktop Maya root, legacy
workspace root, project roots, preferred/blocked audio names, browser driver,
and voice defaults. Existing `.env` names remain compatible. Historical memory,
profile facts, and project notes are deliberately not config. **Sev 1-2.**

### W4 — Flat 724-file root — open, gating, now root-growth guarded
Independent count on 2026-06-12: **724 top-level `.py` files**. The old 300-line
gate prevented oversized files but also encouraged splitting into more root
helpers. `code_health.py` now reports `root_py_files: 724/724` and treats any
further root growth as a blocking violation. This does not close W4; it only
stops the hole from getting deeper. The real fix remains package boundaries:
start with `maya_memory/`, then `harness/`, `browser/`, `documents/`, keeping
compatibility wrappers while imports migrate. Public release = a **separate
hardened repo** seeded from the restructured core, no personal wiring. **Sev 4**,
pre-public.

### W5 — Credentials / sandbox — provider added, real-secret migration still open
Two halves. (a) Keys → macOS Keychain — provider is now implemented in
`secret_provider.py` with `env`, `keychain`, and `auto` modes. Default stays
`env` during transition, and `config.get_env/require_env` route through the
provider. A throwaway macOS Keychain read/write/delete check passed on this
iMac; the migration helper copies named env secrets into Keychain only when
called explicitly. (b) Tool sandboxing — still large, pre-public, stage by blast
radius: shell → repo writes → **browser** → file deletes. **Sev 4 until live
Keychain migration and sandboxing are done.**

### W6 — Browser — driver SOLVED-BY-CHOICE, surface migrated to W7+W5

**W6 is two separate problems. Do not treat "extension bridge is good" as
"the browser is handled" — only the driver half is.**

**(a) The driver — HOW Maya controls the browser → good, council's CDP/Playwright
recommendation is SUPERSEDED.** The concurrent session is migrating to a Chrome
**extension bridge** (`browser_extension_bridge.py`, `ExtensionBrowserController`)
behind the same `make_browser_controller` interface, with
`MAYA_BROWSER_DRIVER=auto|extension|applescript` modes. This is a legitimate —
arguably *better* — answer than the original Playwright/CDP suggestion:
- A Chrome extension is **cross-platform by nature** (runs wherever Chrome runs),
  so it addresses the council's cross-platform blocker more cleanly than Playwright.
- It drives the user's **real logged-in browser**, not a separate automation
  profile — which suits heavy real-world browsing.
- **Verdict: stop pursuing CDP/Playwright.** The extension path is the right call.

  **Field evidence (corrects "chosen and in progress" — it IS proven):** the
  checklist records live extension reliability nights — `night2` 95%,
  `night3-rerun` 91.7%, `night4_extension_rerun` **96.7%**, all with **10/10
  safety stops and zero criticals**. So the extension driver is not just chosen,
  it has real live-Chrome reliability data. The remaining gap is not capability —
  it is **public-cleanliness**:
  - The **AppleScript fallback still exists**, but it is now explicit legacy:
    `MAYA_BROWSER_DRIVER=legacy`. Normal mode is strict extension, so a missing
    extension fails loudly instead of quietly opening ungrouped tabs.
  - The one-more-run gate passed on `w6_extension_full_after_context_fix_20260611`
    with 96.7% completion, 10/10 safety stops, zero criticals, and all benchmark
    lanes passing.

**(b) The surface — the browser as an injection/attack vector → did NOT disappear,
it MIGRATED.** The dangerous half of W6 was never the driver; it is that a
heavily-used browser is Maya's #1 prompt-injection entry point. That risk is now
  tracked and closed under:
- **W7** — the untrusted-input boundary. Browser page text and extension page
  inspection now carry untrusted flags into observations and permission checks.
- **W5** — the browser must run **inside the sandbox**.

**So: W6's driver problem is solved by choice; W6's risk problem is now W7-live +
W5-sandbox. Same attack surface, different ticket.** Net for this file: don't
spend effort on the driver beyond optional AppleScript legacy removal;
the browser only becomes safe to point at untrusted sites once W7 entry-tagging is
live and the sandbox exists. **Sev 2** for the driver (surface risk remains W7+W5).

### W7 — Untrusted-input boundary — live-wired for current surfaces
The fail-open vocabulary bug is fixed: "external/scope-widening" now resolves
from the registry's `side_effect_level ∈ {external, repo_write}` with action-name
fallback, and **unknown actions fail closed** (treated as external). The kernel
(`check`) takes optional `untrusted_influence`/`injection_detected` flags
(default off → byte-identical), applies the boundary after its base decision,
and can only tighten. Entry tagging now exists in browser page parsing, Chrome
extension page inspection, screen summaries, active-context extraction from
browser/Office/Markdown/screen fallback, harness observations, LangGraph tool
checks, and SDK tool calls. Smokes: `untrusted_input_boundary_smoke.py` and
`untrusted_live_path_smoke.py`. **Honest limit (unchanged):** regex detection is
bypassable; the robust protection is the influence-gate (any external send under
untrusted influence forces a human gate regardless of a matched pattern).

### W8 — Multi-tenant isolation — dissolved
Self-host-per-user → separate process → separate DB → cross-tenant leakage is
structurally impossible. No work unless you ever run a hosted service. **Sev 1.**

---

## Next steps (do in this order)

1. **Run live W7 injection checks** against browser, screen, and active document
   paths whenever those surfaces change. The code is wired; live evidence should
   keep it honest.
2. **Keep Keychain as the preferred live secret source.** Provider secrets and
   Telegram token are migrated; `.env` remains rollback fallback while
   sandboxing matures.
3. **Improve W2 recall with data, not config flipping.** Supersede history is
   built; the current eval still does not justify enabling embedding rerank by
   default.
4. **Optional W6 cleanup:** remove the AppleScript legacy path only after deciding
   there is no local browser fallback still worth keeping.
5. **Then the big pre-public rocks** (only when a public date is real):
   sandbox (W5), package restructure + clean public repo (W4).

---

## The Gate — do NOT onboard a second human until ALL hold
- Tool execution sandboxed (W5).
- Read-surfaces can't widen scope / trigger external sends unprompted —
  **W7 entry-tagging LIVE** for browser/screen/document paths, with regression
  smokes kept green.
- Credentials encrypted at rest (W5).
- Public codebase = separate restructured repo, no personal wiring (W4).
- Browser cross-platform — satisfied for normal mode by strict extension default
  and the 96.7% extension reliability run. AppleScript legacy removal remains
  cleanup before public release.
- ~~Per-user isolation~~ — **satisfied** by self-host-per-user (W8).

Done: W1 ✅, isolation ✅, W7 live path ✅, W3 main config ✅, W5 provider +
Keychain migration ✅, W6 strict extension ✅.
Open: W5 execution sandbox maturity, W4 clean public repo, optional AppleScript
legacy removal, W2 retrieval quality.

---

## Score — before vs. after

| Capability | Now | All fixed | Note |
| --- | :---: | :---: | --- |
| Harness / orchestration | 8 | 9 | sandbox + clean structure on strong spine |
| Governance & safety | 9 | 10 | W7 live + sandbox + encrypted creds + fail-closed verifier |
| Memory — governance | 9 | 9 | near ceiling |
| Memory — retrieval intelligence | 5 | 8 | rerank + links + temporal; entity graph deferred |
| Agentic loop / autonomy | 5 | 8 | W1 verifier done; native tool-calling to come; bounded by design |
| Model routing | 7 | 8 | cost-aware tier + fallback chains |
| Artifact quality (Office) | 8 | 8 | not a weakness |
| Distribution / usability | 3 | 8 | cloneable + installer + cross-platform; polish/adoption gate the last 2 |
| Engineering discipline | 8 | 9 | packages + tests/ + cross-platform CI |
| **Overall** | **~7.2** | **8.5–9** | |

- **Today ≈ 7.6-7.8** — W1 verifier is closed, W7 is live-wired for current
  read surfaces, W3 runtime config exists, W5 has a secret provider, and W6 is
  strict-extension by default. The remaining ceiling is held back by sandboxing,
  W4 structure, and W2 recall quality.
- **After this remediation ≈ 7.6-7.8** — W7 is live, W3 is centralized, W5 has a
  provider, and W6 is strict-extension by default. The remaining score ceiling is
  held back by sandboxing, W4 structure, and W2 recall quality.
- **Ceiling 8.5–9**, not 10: bounded autonomy is a deliberate design choice that
  protects the governance moat; the last point of distribution/retrieval is
  post-launch adoption + an entity graph justified by real scale — time, not code.

---

## One line for the next session
Do not re-open W7 from scratch. Keep `untrusted_live_path_smoke.py` green, add
new entry surfaces to the same boundary, migrate one secret to Keychain in a
controlled test, and run the next browser extension reliability pass before
removing AppleScript legacy mode. Save sandbox/restructure for a real public date.
