# Cloud Solution Architecture Knowledge Base

Truth layer for Maya's cloud solution-architect skill. Answers about designing,
migrating, securing, costing, and operating workloads on AWS, GCP, and Azure
must be grounded in a recipe or concept doc from this tree when one exists.

The pack is PROVIDER-NEUTRAL FIRST: every recipe states the pattern once, then
maps it to the AWS / GCP / Azure services that implement it. This mirrors how a
working solution architect thinks — pattern first, vendor second.

## Rules

1. Designs are justified, never asserted. Every architecture choice names the
   requirement it serves (availability target, RTO/RPO, latency, cost, compliance)
   and the trade-off it accepts.
2. Recipes are the worked units. Each recipe is retrieved whole: a design
   without its red flags and limitations is not an answer.
3. Honesty bar: cloud services, limits, and prices change monthly. Numbers here
   are illustrative method inputs; real pricing/quotas/SLAs must be checked
   against the provider's current documentation and calculators. Maya must say
   when an answer leans on general model knowledge instead of a recipe.
4. No cloud credentials, access keys, service-account keys, or connection
   strings ever enter this tree or any artifact built from it.
5. Nothing here is applied to a live cloud environment without explicit
   approval — designs and IaC are drafts until Zainal confirms.

## Mandatory recipe format

Every file under `recipes/` follows this contract:

- `## Intent` — the question this recipe answers.
- `## Inputs Required` — the data needed, with placeholders in CAPS.
- `## Method` — numbered steps with explicit decision criteria.
- `## Worked Example` — a complete pass on a realistic scenario, with the
  AWS / GCP / Azure service mapping.
- `## Interpretation` — what the resulting design guarantees and what it does not.
- `## Red Flags` — the patterns an experienced architect would catch.
- `## Limitations` — what this pattern cannot solve.

## Layout

| Path | Use |
| --- | --- |
| `recipes/architecture/` | Workload patterns: three-tier web app, serverless event-driven, landing zone |
| `recipes/resilience/` | High availability & disaster recovery (RTO/RPO tiers) |
| `recipes/cost/` | Cost optimization review (FinOps) |
| `recipes/migration/` | Migration assessment (the 6 Rs) |
| `recipes/security/` | IAM least-privilege review |
| `concepts/` | Reference: well-architected principles, AWS↔GCP↔Azure service map, cloud networking, identity & access |

## Verified bar

A recipe is "verified" when its design has been reviewed against the current
provider documentation (services and limits drift). Until then Maya may use it
but should not present its outputs as independently verified.
