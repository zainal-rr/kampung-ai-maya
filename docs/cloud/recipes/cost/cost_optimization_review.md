# Cloud Cost Optimization Review (FinOps)

## Intent

Find and rank the savings in a cloud bill methodically — visibility first,
then waste, then rate, then architecture — instead of guessing.

## Inputs Required

- The BILL: cost by service and by account/project/subscription, 3+ months.
- TAGGING state: can cost be attributed to team/workload/environment?
- UTILIZATION data: CPU/memory of compute, storage access patterns.
- COMMITMENT state: existing reserved instances / savings plans / CUDs.

## Method

Work the four layers IN ORDER — each depends on the one before:

1. **Visibility:** enforce tagging/labels (team, workload, env); set budgets
   and anomaly alerts (Cost Explorer+Budgets / GCP Billing+BigQuery export /
   Cost Management). You cannot optimize what you cannot attribute.
2. **Waste (usage reduction):** the classic offenders, biggest first —
   - Idle compute: <10% CPU for weeks → downsize or delete.
   - Non-prod running 24/7 → schedule off nights/weekends (~65% of the week
     is non-working hours).
   - Unattached volumes, old snapshots, idle load balancers and NAT gateways,
     unassociated IPs.
   - Storage on the wrong tier → lifecycle policies to infrequent-access /
     archive classes by access pattern.
   - Oversized databases and over-provisioned IOPS.
3. **Rate (price reduction)** — only after usage is clean (never commit to
   waste): commitments for the stable baseline — AWS Savings Plans/RIs, GCP
   committed use discounts, Azure reservations + Hybrid Benefit. Spot/
   preemptible for fault-tolerant batch (steep discounts, eviction risk).
4. **Architecture:** serverless for spiky loads, autoscaling floors lowered,
   caching/CDN to cut egress, data-transfer paths reviewed (cross-AZ/region
   traffic is a silent line item), managed services replacing self-run fleets.

## Worked Example

Monthly bill RM100k: compute RM55k, database RM20k, storage RM12k, egress
RM8k, other RM5k. Tags exist for 70% of spend.

- Visibility: close the 30% untagged gap first (policy: untagged = flagged).
- Waste pass: utilization shows 30% of compute idle/oversized → rightsizing
  ≈ RM12k; non-prod (40% of compute) scheduled off-hours ≈ RM9k; storage
  lifecycle to cold tiers ≈ RM4k. Waste subtotal ≈ **RM25k (25%)**.
- Rate pass: post-cleanup stable baseline ≈ RM40k of compute/database →
  1-year commitments at typical ~30–40% discount ≈ **RM13k**.
- Architecture pass: CDN in front of egress-heavy API ≈ RM3k.
- Total identified ≈ **RM41k/month (~41%)** — in line with the common finding
  that a first serious review yields 30–40%. Each number must be re-priced in
  the provider's current calculator before being promised.

## Interpretation

- Rank fixes by savings ÷ effort; schedule-off and rightsizing usually win.
- A commitment is a bet on the baseline: commit to ~80% of the post-cleanup
  stable floor, never to the peak, never before the waste pass.
- Re-review quarterly — cloud waste regrows like grass.

## Red Flags

- Buying reservations before rightsizing (locking in the waste).
- Untagged spend above ~10% (attribution is the control plane of FinOps).
- Egress and cross-AZ transfer ignored because they're "small lines" (they
  compound with scale).
- A one-time "cost project" with no recurring review or ownership.

## Limitations

Savings estimates here are method illustrations — actual discount rates,
tiers, and prices change constantly and differ by region; the provider's
current pricing calculator is the only honest source. Deep architecture
changes (re-platforming to serverless) carry engineering cost this review
sizes but cannot decide.
