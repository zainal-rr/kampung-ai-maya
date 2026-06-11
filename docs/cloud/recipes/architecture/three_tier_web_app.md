# Three-Tier Web Application Architecture

## Intent

Design a standard web/presentation + application + data architecture on AWS,
GCP, or Azure that meets a stated availability target without gold-plating.

## Inputs Required

- AVAILABILITY target (e.g. 99.9% vs 99.99%) and acceptable RTO/RPO.
- TRAFFIC profile: requests/sec baseline and peak, growth, geography of users.
- STATE: relational vs NoSQL, data size, read/write ratio.
- COMPLIANCE constraints (data residency, encryption requirements).
- Monthly BUDGET ceiling, if one exists.

## Method

1. **Entry tier:** DNS → CDN (static assets, TLS at edge) → load balancer in
   public subnets. The LB is the only internet-facing component.
2. **Application tier:** stateless compute in PRIVATE subnets across ≥2
   AZs/zones, in an auto-scaling group/MIG/VMSS (or containers). Stateless is
   the rule: sessions go to a cache or signed tokens, never instance memory.
3. **Data tier:** managed relational database in private subnets, multi-AZ
   standby for 99.9%+; add read replicas only when read load (not fashion)
   demands. Cache hot reads (Redis) in front.
4. **Sizing:** instances ≈ peak RPS / per-instance RPS (load-tested), then +1
   for N+1 redundancy per AZ. Scale on a leading metric (CPU or queue depth).
5. **Security:** tier-to-tier security groups (LB→app port only, app→DB port
   only), private endpoints for object storage, secrets from the secret
   manager, encryption at rest and in transit everywhere.
6. **Operations:** IaC for the whole stack, centralized logs/metrics/alarms,
   automated DB backups with tested restore.

## Worked Example

Requirement: 99.9% availability, 500 RPS peak, relational data, single region.

- Topology: 2 AZs; public subnets hold only the ALB; app tier 4 instances
  (load test showed ~150 RPS/instance → 500/150 = 3.3 → 4, giving N+1) in an
  auto-scaling group 4–8; Multi-AZ managed Postgres + 1 Redis cache; object
  storage via private endpoint for uploads.
- Service mapping:
  - AWS: Route 53 → CloudFront → ALB → EC2 ASG → RDS Multi-AZ + ElastiCache + S3
  - GCP: Cloud DNS → Cloud CDN → Global LB → MIG → Cloud SQL HA + Memorystore + GCS
  - Azure: Azure DNS → Front Door → App Gateway → VMSS → Azure SQL zone-redundant + Azure Cache + Blob
- Why this meets 99.9%: every tier survives one AZ loss (LB cross-AZ, ASG
  spans AZs, DB fails over to standby). It does NOT survive region loss — the
  requirement didn't pay for that (see `resilience/high_availability_dr.md`).

## Interpretation

- This design guarantees: no single point of failure within the region,
  horizontal scale to the ASG max, recovery from AZ failure in minutes.
- It does not guarantee: region-loss survival, zero-downtime DB failover
  (expect ~60–120s), or protection from bad deploys (that's release process).
- Cost honesty: the multi-AZ DB standby roughly doubles database cost — that
  is the price of the availability target, and pricing must be checked against
  the provider's current calculator, not assumed.

## Red Flags

- State on app instances (sessions, local uploads) — breaks scaling and AZ failover.
- Database in a public subnet or reachable from the internet.
- Auto-scaling configured but never load-tested (the per-instance RPS is a guess).
- 99.99% promised on a single-region design — the arithmetic rarely closes.
- One giant instance instead of small horizontal ones ("vertical comfort").

## Limitations

Three-tier fits request/response web workloads. Bursty/event-driven work fits
`serverless_event_driven.md` better; many small teams should start serverless
or PaaS and only adopt this shape when load and control needs justify it.
