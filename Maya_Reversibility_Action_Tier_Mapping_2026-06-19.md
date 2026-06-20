# Reversibility Action-Tier Mapping — Step 3 Send-Me-First Artifact

Status: **LOCKED MAPPING / PREDICATES WIRED THROUGH KERNEL / ROUTER FREE-ROUTING NOT EXPANDED**
Date: 2026-06-19
Source: current `default_maya_tool_registry()` at product commit `61cd2fb`
Parent taxonomy: `Maya_Reversibility_Taxonomy_2026-06-19.md`

This maps every current `MayaToolSpec` registry tool to Tier R or Tier I before any Step 3 code is written.

Review lock: **LOCKED 2026-06-19** with reviewer rulings:

1. `browser.inspect` is current-page inspection only in v1. No owner-supplied URL navigation is free-routed.
2. `pptx.create` stays Tier I in v1 because `cost_risk=high`; budget confirmation is separate from reversibility.
3. `skill.activate` stays Tier I in v1; future-behavior changes are not reversible-by-default.
4. `blender.create_model` stays Tier I in v1; provider cost and external/physical follow-on risk outweigh v1 utility.

Predicate implementation was reviewed, locked, and wired through the permission kernel on 2026-06-19.

Kernel wiring intent: **preserve-free / tighten-risk**. The Step 3 kernel layer
does not override a stricter W7, disclosure, source-trust, cost, sandbox, or
approval decision. It preserves `allow` for contained reversible candidates that
the base kernel already allows, and it tightens locked Tier I or failed
containment predicates to `confirm`. Broader router-level utility optimization
is a separate follow-on only after this kernel behavior is accepted.

## Load-Bearing Rules

1. Reversibility only relaxes the confirmation/friction gate. It does not relax source-trust, content-vs-control, disclosure, cost, replay, or W7 untrusted-input boundaries.
2. A reversible action may run free on an untrusted trigger, but an untrusted value may not choose a path, URL, filename, app, sheet, tab, click target, recipient, account, repo path, command args, or disclosure destination.
3. Unknown tools, unknown side effects, missing conformance rows, and unresolved handler paths default to Tier I.
4. Any Step 0b-unproven handler/path with an irreversible or disclosure branch remains Tier I until conformance proves the safe branch is internal-gated or split.
5. `cost_risk` is a separate gate. A tool can be Tier R for security friction but still require budget confirmation.
6. `replay_safe=False` does not automatically make a tool Tier I, but it requires idempotency/post-condition handling before repeated execution.

## Tier Legend

- **Tier R**: reversible/contained. May bypass the extra confirmation friction only when all listed conditions hold.
- **Tier R-C**: conditionally reversible. Must be split by arguments/handler path before free-routing.
- **Tier I**: irreversible/external/high-blast-radius. Strict gate stays.

## Full Current Registry Mapping

| Tool | Registry evidence | Proposed tier | Free-routing conditions | Gate remains for | Rationale |
|---|---|---:|---|---|---|
| `screen.capture` | `permission_scope=follow_up`, `side_effect_level=read`, `cost_risk=none`, `replay_safe=True`, lane `sight` | **Tier R** | Capture/inspect current local screen only; answer/disclosure output still destination-gated. | Any disclosure of private screen contents to untrusted destination; any follow-on action from screen text. | Read-only local observation is undoable; the risk is disclosure or target laundering, handled by separate gates. |
| `browser.inspect` | `permission_scope=browse_web`, `side_effect_level=read`, `cost_risk=low`, `replay_safe=True`, lane `sight` | **Tier R-C** | Inspect/read the already-loaded current page only, without clicking, submitting, logging in, downloading, or mutating remote state. | Any requested navigation, owner-supplied URL, untrusted URL, private/logged-in page disclosure, paid/high-cost browsing. | Reading the current page is reversible; choosing a URL is a control value and not freed in v1. |
| `browser.click` | `permission_scope=browser_click`, `side_effect_level=write`, `cost_risk=none`, `replay_safe=False`, lane `sight` | **Tier R-C / default Tier I until split** | Only link-navigation/read-only/no-submit clicks inside Maya browser boundary after classifier proves no remote mutation. | Submit, login, payment, booking, purchase, upload, download/open arbitrary file, permission prompt, destructive UI, or untrusted click target. | Browser clicks are not inherently undoable; Step 3 must split safe navigation from effectful clicks. |
| `file.create` | `permission_scope=create_file`, `side_effect_level=write`, `cost_risk=none`, `replay_safe=False`, lane `local` | **Tier R-C** | Create a new local file inside Maya-owned workspace with Maya-derived safe slug/path; no overwrite; restorable; not delivered/opened to external actor. | Untrusted path/name, overwrite, protected path, move out of workspace, file consumed by another process before undo. | Local contained creation is the main utility win, but path/name is a control value. |
| `docx.create` | `permission_scope=create_document`, `side_effect_level=write`, `cost_risk=medium`, `replay_safe=False`, lane `documents` | **Tier R-C** | Create undelivered local docx in Maya artifact folder; title/path Maya-derived; content allowed by source-trust/disclosure policy; budget permits. | External send/share/present; untrusted title/path as control target; private content; QA failure; high-cost budget policy. | Draft artifact is reversible until delivery or disclosure. |
| `xlsx.create` | `permission_scope=create_document`, `side_effect_level=write`, `cost_risk=medium`, `replay_safe=False`, lane `documents` | **Tier R-C** | Create undelivered local xlsx in Maya artifact folder; sheet names/paths Maya-derived or owner-literal; budget permits. | External send/share/present; untrusted sheet/tab/path; formulas/macros/remote loads; private content; high-cost budget policy. | Local spreadsheet draft is contained only if names/formulas do not create a hidden control channel. |
| `pptx.create` | `permission_scope=create_presentation`, `side_effect_level=write`, `cost_risk=high`, `replay_safe=False`, lane `documents` | **Tier I in v1** | None for Step 3. | All PPTX creation remains confirmation/budget-gated in v1; present/send/share/export, remote media/scripts, and private/disclosure content remain gated. | Draft deck may be reversible, but high cost makes budget confirmation a separate mandatory gate in v1. |
| `memory.write` | `permission_scope=follow_up`, `side_effect_level=write`, `cost_risk=none`, `replay_safe=False`, lane `memory` | **Tier R-C** | Owner-authored memory or Maya-process note with correct provenance; write remains supersedable/forgettable; not used as trusted control unless provenance allows. | Relayed/untrusted memory, target/account/recipient values from untrusted content, resurrection of superseded facts, private disclosure. | Memory write is locally reversible, but memory provenance is security-critical and not relaxed by Step 3. |
| `skill.activate` | `permission_scope=follow_up`, `side_effect_level=write`, `cost_risk=none`, `replay_safe=True`, lane `skills` | **Tier I in v1** | None for Step 3. | Enabling/disabling/deleting skills, installing/scaffolding, changing future behavior, selecting skill from untrusted content, unknown skill. | Skill state affects future capability; default strict gate until a contained non-persistent selection branch is separately proven. |
| `blender.create_model` | `permission_scope=create_file`, `side_effect_level=write`, `cost_risk=medium`, `replay_safe=False`, lane `artisan` | **Tier I in v1** | None for Step 3. | Physical print/order, external upload/share, untrusted output path, unsafe model content, provider cost, high-cost budget threshold. | Artisan generation has provider cost and possible external/physical follow-on risk; v1 utility is too low to spend risk budget here. |
| `mcp.call` | `permission_scope=run_command`, `side_effect_level=external`, `approval_required=True`, `cost_risk=medium`, `replay_safe=False`, lane `artisan` | **Tier I** | None for Step 3. | All calls remain gated unless future per-server/tool registry proves a read-only, contained, non-disclosure subtool. | Generic MCP can cross boundaries; recent live testing found a broad `mcp.call` gate hole, so fail closed. |
| `repo.apply_patch` | `permission_scope=apply_code_patch`, `side_effect_level=repo_write`, `approval_required=True`, `cost_risk=none`, `replay_safe=False`, lane `artisan` | **Tier I** | None for Step 3. | All repo writes, code changes, commits/pushes/deploy-related work. | Repo write is durable and can affect runtime/security; strict gate stays. |
| `telegram.send_file` | `permission_scope=share_file`, `side_effect_level=external`, `approval_required=True`, `cost_risk=none`, `replay_safe=False`, lane `telegram` | **Tier I** | None for Step 3. | Every send/share/attach/delivery path. | Leaves Maya boundary and can disclose private content; strict approval remains. |

## Initial Implementation Shape Implied By This Mapping

Do not implement by simply allowing all `side_effect_level=write`.

Step 3 needs one small policy helper, not a policy-engine rewrite:

1. Resolve tool by registry.
2. If tool maps Tier I → current gate unchanged.
3. If tool maps Tier R-C → check the tool-specific containment predicate.
4. If containment predicate passes → friction gate can relax.
5. Still run W7/source-trust/disclosure/cost/idempotency checks.

Field-source wiring requirement:

- Predicate inputs must receive control-field provenance from Maya's trusted provenance ledger/slugger layer.
- Planner/tool-call payload labels such as `path_source`, `filename_source`, or `field_sources` are not trusted.
- A planner-forged source label must not make an untrusted control value free-routable.

Suggested predicates:

- `is_contained_artifact_create(tool, args, provenance, field_provenance=trusted_field_sources)`
- `is_current_page_browser_inspect(tool, args, browser_context)`
- `is_owner_authored_memory_write(args, provenance)`

Anything without a predicate remains Tier I.

Implemented predicate artifact for review:

- Code: `maya_core/reversibility_predicates.py`
- Smoke: `tests/smokes/reversibility_predicates_smoke.py`
- Kernel wiring: `maya_core/maya_permission_kernel.py`
- SDK wiring proof: `maya_core/maya_harness_sdk.py` and `tests/smokes/maya_harness_sdk_smoke.py`
- CI hooks: `local_ci.py` checks named `reversibility predicates`, `reversibility gate wiring`, and `Maya harness SDK`
- Integration status: **wired as a permission-kernel tightening layer; no router-specific free-routing expansion beyond the kernel**

## Must-Succeed / Must-Fail Twins For This Mapping

Must succeed without extra confirmation:

- `screen.capture`: inspect current screen.
- `browser.inspect`: read current page.
- `file.create`: create a new note in Maya workspace with Maya-generated filename.
- `docx.create` / `xlsx.create`: create undelivered local artifact with Maya-generated path.
- `memory.write`: owner-authored “remember my test color is blue.”

Must remain gated/blocked:

- `telegram.send_file`: attach/send any file.
- `mcp.call`: any generic call, including dangerous `action_type`.
- `repo.apply_patch`: apply repo patch.
- `browser.click`: submit/pay/login/upload/download/open arbitrary file.
- `file.create`: untrusted-supplied path/name or overwrite.
- `memory.write`: relayed external content trying to become owner-trusted target.
- `skill.activate`: enable/disable/delete/install or untrusted-selected skill.
- `pptx.create`: all free-routing remains blocked in v1.
- `blender.create_model`: all free-routing remains blocked in v1.

Orthogonality test:

- Untrusted page asks Maya to “make a note about this” → contained note creation may proceed with Maya-derived safe path.
- Same page supplies `../../sensitive.txt` or “save as Payroll.xlsx” as the filename → target is untrusted control value, so the path/name is rejected or owner-confirmed.

## Coverage Check

Current registry tool count: 13.

Mapped tools:

1. `blender.create_model`
2. `browser.click`
3. `browser.inspect`
4. `docx.create`
5. `file.create`
6. `mcp.call`
7. `memory.write`
8. `pptx.create`
9. `repo.apply_patch`
10. `screen.capture`
11. `skill.activate`
12. `telegram.send_file`
13. `xlsx.create`

Coverage: **13 / 13**

## Predicate And Wiring Lock

Mapping, predicate code, and kernel wiring are locked:

- `browser.inspect` predicate must be current-page-only.
- `file.create`, `docx.create`, and `xlsx.create` predicates must reject untrusted path/name/sheet/tab/app/target control values.
- `memory.write` predicate must require owner-authored or trusted-internal provenance.
- `pptx.create`, `skill.activate`, `blender.create_model`, `browser.click`, `mcp.call`, `repo.apply_patch`, and `telegram.send_file` must remain Tier I in v1.
- `field_provenance` must come from Maya's trusted provenance/slugger layer. Planner/tool-call self-labels such as `path_source="maya_derived"` are ignored.
- The wiring proof must include a forged-source case: an untrusted field provenance plus planner-forged trusted label must require approval.
- The wiring proof must include must-succeed twins: clean reversible creates,
  read-only follow-up, and owner-authored memory writes remain `allow`.

No broader Step 3 router optimization should be written until the current kernel-level behavior is accepted.
