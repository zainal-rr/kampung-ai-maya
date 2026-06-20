# Identity & Access In The Cloud

Identity is the real security perimeter in cloud — most breaches walk through
an over-permissive role, not a firewall.

## The Three Models

- **AWS IAM:** policies (JSON documents of allow/deny on actions + resources +
  conditions) attached to users, groups, and ROLES. Roles are assumed
  temporarily (by humans via SSO, by services via instance profiles /
  IRSA) — long-lived access keys are the anti-pattern.
- **GCP Cloud IAM:** bindings of members (users, groups, service accounts) to
  ROLES (collections of permissions) on a resource hierarchy:
  organization → folders → projects → resources. Policy inherits downward.
- **Azure:** Entra ID (identities, formerly Azure AD) + Azure RBAC (role
  assignments = principal + role definition + scope) over the hierarchy:
  management groups → subscriptions → resource groups → resources. Managed
  identities are the service-principal-without-secrets pattern.

Same shape everywhere: WHO (principal) can do WHAT (actions/role) on WHICH
resource (scope), inherited down a hierarchy.

## Non-Negotiable Principles

1. **Least privilege:** grant the narrowest actions on the narrowest scope.
   Wildcards (`*` on actions or resources, Owner/Editor roles) are findings,
   not conveniences. See `recipes/security/iam_least_privilege_review.md`.
2. **Workload identity over static keys:** services authenticate via assumed
   roles / service accounts / managed identities. A credential that can be
   leaked (access key in code, key file in a repo) eventually will be.
3. **Humans via SSO + MFA, never shared accounts.** Root/Owner accounts:
   locked away, MFA'd, break-glass only, alarmed on use.
4. **Separate duties by environment:** prod and dev in different
   accounts/projects/subscriptions, not just different resource groups —
   blast-radius isolation is structural, not policy-deep.
5. **Audit on by default:** CloudTrail / Cloud Audit Logs / Activity Log
   centralized, immutable, and alerted.

## Secrets

Secrets live in the secret manager (Secrets Manager / Secret Manager /
Key Vault), referenced at runtime, rotated. Never in code, env files committed
to git, IaC variables, or chat logs. Maya never stores cloud credentials in
memory or artifacts — that rule is absolute.
