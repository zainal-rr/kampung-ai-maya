# IAM Least-Privilege Review

## Intent

Audit who/what can do what in a cloud environment and shrink permissions to
the minimum the workload actually uses — the highest-leverage security work in
cloud.

## Inputs Required

- IAM INVENTORY: users, groups, roles, service accounts/managed identities,
  and their attached policies/role bindings, per account/project/subscription.
- USAGE DATA: last-accessed / access analyzer output (AWS IAM Access Analyzer
  & last-accessed data, GCP IAM Recommender, Azure PIM + access reviews).
- The workload's ACTUAL operations (what it really calls in production).

## Method

1. **Find the dangerous grants first**, in this order:
   - Admin-equivalent: `*:*`, Owner/Editor (GCP), Owner/Contributor at
     subscription scope (Azure) — every one is a finding needing justification.
   - Long-lived human credentials: access keys, downloaded service-account
     keys, passwords without MFA. Replace with SSO + assumed roles / workload
     identity / managed identities.
   - PUBLIC or cross-account/external grants: bucket policies, resource shares,
     externally-assumable roles — validate each against intent.
2. **Shrink by evidence, not theory:** compare granted vs USED permissions
   (last-accessed / Recommender). Unused for 90 days → remove. Both Google and
   AWS tooling generate the narrowed policy for you; review and apply.
3. **Privilege escalation paths:** a principal who can edit policies, pass
   roles (`iam:PassRole`), or impersonate service accounts effectively holds
   everything those paths reach — treat policy-editing rights as admin.
4. **Structural fixes** beyond individual grants: separate duty by environment
   (no dev role reaching prod), deploys via pipeline identities instead of
   humans, just-in-time elevation (Azure PIM or equivalent) instead of
   standing admin.
5. Re-run on a schedule; alert on new admin grants and new external access in
   the audit log — review decay is the default state.

## Worked Example

Review of one production account/project finds: 4 principals with
admin-equivalent (2 humans "for convenience", 1 CI role, 1 forgotten vendor),
9 service accounts with downloaded keys, app role granted full storage access
but observed using only read on two buckets.

- Actions: humans → SSO + just-in-time elevation, standing admin removed; CI →
  scoped deploy role (its 90-day usage defined the policy); vendor → access
  ended, audit reviewed for use; keys → workload identity / managed identity,
  keys revoked; app role → generated least-privilege policy (read-only, two
  bucket ARNs/paths).
- Result: admin principals 4 → 0 standing (2 eligible via JIT), key-based
  identities 9 → 0, storage blast radius from "all data" to "two read-only
  paths". Each change shipped through IaC with a rollback diff.

## Interpretation

- Success metric is BLAST RADIUS: what can the most-compromised single
  credential reach? Re-ask after every change.
- Findings are ranked: external/public access and admin-with-keys outrank a
  slightly-broad read role. Fix order follows risk, not alphabetical.

## Red Flags

- "Temporary" admin that outlived its incident.
- Service-account key files in repos, laptops, or CI variables.
- One role shared by many workloads ("the app role") — blast radius bundling.
- Wildcards introduced by IaC modules nobody reviewed.
- Access reviews that always conclude "keep all" (rubber-stamp decay).

## Limitations

Usage-based narrowing can break RARE legitimate paths (year-end jobs, DR
runbooks) — stage removals with monitoring and a fast rollback. Tooling names
and capabilities (Access Analyzer, Recommender, PIM) evolve; verify current
behavior. This reviews CLOUD IAM — application-level authorization inside the
workload is a separate audit.
