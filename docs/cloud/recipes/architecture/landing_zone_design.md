# Landing Zone Design (Multi-Account/Project Foundation)

## Intent

Design the organizational foundation — accounts/projects/subscriptions,
guardrails, networking, identity — BEFORE workloads arrive, so growth doesn't
require re-platforming.

## Inputs Required

- ENVIRONMENTS needed (prod, staging, dev, sandbox) and TEAMS/workload count.
- COMPLIANCE requirements (data residency, audit retention, regulated industry).
- HYBRID needs: on-prem connectivity, existing identity provider.
- Central platform team capacity (a landing zone someone must operate).

## Method

1. **Isolation structure** — separate blast-radius domains structurally:
   - AWS: Organization → organizational units (Security, Infrastructure,
     Workloads/Prod, Workloads/NonProd, Sandbox) → one ACCOUNT per
     workload+environment.
   - GCP: Organization → folders (same shape) → one PROJECT per workload+env.
   - Azure: Management groups (same shape) → SUBSCRIPTIONS per workload+env.
   Environment isolation is account/project-level, never just tags.
2. **Guardrails as policy, not promises:** AWS Service Control Policies / GCP
   Organization Policies / Azure Policy. Baseline set: deny disabling audit
   logs, deny public storage by default, restrict regions for residency,
   require encryption.
3. **Identity:** federate the existing IdP via SSO (IAM Identity Center /
   Cloud Identity / Entra ID); permission sets per role per environment;
   break-glass root accounts vaulted, MFA'd, and alarmed.
4. **Network:** hub-and-spoke (Transit Gateway / NCC / vWAN), CIDR plan for
   the whole org up front, centralized egress and inspection in the hub,
   shared private DNS (see `concepts/cloud_networking.md`).
5. **Logging:** organization-wide audit trail to a locked, dedicated
   log-archive account/project with retention matching compliance.
6. **Vending:** new account/project creation is automated IaC (Control Tower /
   project factory / subscription vending) with the baseline pre-applied —
   never hand-built.

## Worked Example

Mid-size org: 6 workloads × prod+nonprod, on-prem AD, residency restricted to
one geography.

- Structure: ~15 accounts/projects — 12 workload + security (audit/log
  archive), shared-services/network hub, sandbox. OU/folder tree by
  environment class.
- Guardrails: region-restriction policy (residency), public-bucket deny,
  audit-log-tamper deny, root/Owner use alarmed.
- Identity: AD federated via SSO; per-team permission sets (developer in dev,
  read-only in prod; deploys via pipeline roles, not humans).
- Network: hub with VPN-then-dedicated-circuit to on-prem; 10.0.0.0/8 carved
  /16-per-account; spokes have no internet gateways — all egress via hub.
- AWS = Control Tower + this OU shape; GCP = org + folders + project factory
  (Terraform); Azure = ALZ reference architecture (management groups + Policy).

## Interpretation

- This guarantees: a new workload lands in a pre-governed container in
  minutes; one team's mistake cannot reach another's environment; auditors
  get one log location and provable guardrails.
- It does not guarantee: well-architected workloads INSIDE the containers
  (that's the per-workload recipes), or cost control beyond visibility
  (tagging + budgets give the data; humans act on it).

## Red Flags

- Everything in one account/project "for now" — the most expensive deferral in
  cloud; migration later is a re-platform.
- Environment separation by naming convention or tags instead of structure.
- Guardrails in a wiki instead of in Policy/SCP (a promise is not a control).
- Shared admin credentials, or root used for daily work.
- A landing zone designed but unstaffed — it is a product the platform team
  operates, not a one-time setup.

## Limitations

Provider blueprints (Control Tower, GCP foundation, Azure ALZ) evolve —
verify current names/features before committing. A solo-founder/single-team
startup can defer most of this: start with 2–3 accounts (prod, nonprod,
security) and grow the tree when teams arrive.
