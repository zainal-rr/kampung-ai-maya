# Kampung AI Extensibility And Audit Checklist

This checklist tracks the Hermes comparison follow-up: MCP ecosystem, skill import, starter catalog, real learning loop, admin visibility, and MCP-style security manifests.

## 1) Security Manifest

1) [x] Add security manifest schema.
2) [x] Add manifest validator.
3) [x] Track read files permission.
4) [x] Track write files permission.
5) [x] Track delete files permission.
6) [x] Track send files permission.
7) [x] Track browse web permission.
8) [x] Track browser click permission.
9) [x] Track form fill permission.
10) [x] Track account use permission.
11) [x] Track external API permission.
12) [x] Track memory write permission.
13) [x] Track artifact creation permission.
14) [x] Track approval requirements.
15) [x] Track hard blocked actions.
16) [x] Attach manifests to built-in skills.
17) [x] Attach manifests to imported skills.
18) [x] Attach manifests to MCP tools.
19) [x] Block activation if a custom skill lacks a manifest.
20) [x] Add manifest audit command.
21) [x] Add manifest smoke test.

## 2) MCP Ecosystem

1) [x] Add MCP registry storage.
2) [x] Store MCP name.
3) [x] Store MCP command.
4) [x] Store MCP environment needs.
5) [x] Store MCP enabled state.
6) [x] Store MCP permission scope.
7) [x] Store MCP owner.
8) [x] Store MCP last used time.
9) [x] Add MCP proposal flow.
10) [x] Add MCP approval flow.
11) [x] Add MCP enable flow.
12) [x] Add MCP disable flow.
13) [x] Add MCP usage audit log.
14) [x] Support show MCP tools.
15) [x] Support show disabled MCP tools.
16) [x] Support audit MCP X.
17) [x] Support disable MCP X.
18) [x] Add MCP smoke test.

## 3) Skill Import Standard

1) [x] Add local skill folder import.
2) [x] Parse `SKILL.md`.
3) [x] Extract skill name.
4) [x] Extract description.
5) [x] Extract trigger phrases.
6) [x] Extract tool requirements.
7) [x] Extract permission needs.
8) [x] Store imported skill as proposed.
9) [x] Copy imported skill into `maya_skills/proposed`.
10) [x] Create imported skill manifest.
11) [x] Do not activate imported skills automatically.
12) [x] Add import smoke test.
13) [x] Support `npx skills add owner/repo`.
14) [x] Run `npx` imports in a temporary folder.
15) [x] Reject unsafe package strings.
16) [x] Import external skills as proposed only.

## 4) Starter Skill Catalog

1) [x] Create private starter catalog.
2) [x] Add flight research skill.
3) [x] Add shopping comparison skill.
4) [x] Add browser research skill.
5) [x] Add document critique skill.
6) [x] Add slide critique skill.
7) [x] Add network troubleshooting skill.
8) [x] Add finance tracker skill.
9) [x] Add habit planning skill.
10) [x] Add app control skill.
11) [x] Add Excel tracker skill.
12) [x] Include trigger examples.
13) [x] Include non-trigger examples.
14) [x] Include tools needed.
15) [x] Include permissions.
16) [x] Include safety stops.
17) [x] Include tests.
18) [x] Add catalog smoke test.

## 5) Stronger Real Learning Loop

1) [x] Add skill performance analyzer.
2) [x] Count repeated successes.
3) [x] Count repeated failures.
4) [x] Detect user corrections.
5) [x] Detect blocked steps.
6) [x] Detect stale unused skills.
7) [x] Repeated failure creates improvement proposal.
8) [x] Repeated success creates trigger strengthening proposal.
9) [x] User correction creates memory proposal.
10) [x] Record before and after test needs.
11) [x] Do not change active behavior without approval.
12) [x] Add performance analyzer smoke test.

## 6) Private Maya Desk

1) [x] Add Maya desk report builder.
2) [x] Save report to Desktop Maya reports.
3) [x] Show active workflows.
4) [x] Show pending approvals.
5) [x] Show latest artifacts.
6) [x] Show active skills.
7) [x] Show proposed skills.
8) [x] Show disabled skills.
9) [x] Show recent memory writes or user model entries.
10) [x] Show recent MCP usage.
11) [x] Show cost summary.
12) [x] Show recent failures.
13) [x] Support show Maya desk.
14) [x] Support refresh Maya desk.
15) [x] Support open Maya desk.
16) [x] Add Maya desk smoke test.

## 7) Docs And Tests

1) [x] Update `KAMPUNG_AI.md`.
2) [x] Update `KAMPUNG_AI_CHECKLIST.md`.
3) [x] Run `security_manifest_smoke.py`.
4) [x] Run `mcp_registry_smoke.py`.
5) [x] Run `skill_import_smoke.py`.
6) [x] Run `starter_skill_catalog_smoke.py`.
7) [x] Run `skill_performance_analyzer_smoke.py`.
8) [x] Run `maya_desk_smoke.py`.
9) [x] Run `code_health.py`.
10) [x] Run `may1_rehearsal.py`.
11) [x] Keep every Python file under 300 lines.
