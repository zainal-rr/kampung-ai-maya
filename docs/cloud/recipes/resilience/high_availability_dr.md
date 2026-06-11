# High Availability & Disaster Recovery (RTO/RPO Tiers)

## Intent

Choose the right availability/DR tier from the business's actual RTO and RPO,
and design it — paying for the requirement, not for fear.

## Inputs Required

- RTO: how long the business survives the workload being DOWN.
- RPO: how much DATA loss is tolerable (minutes? hours? zero?).
- Cost of downtime per hour (justifies or kills the higher tiers).
- Statefulness: where the truth lives (database, object storage, queues).

## Method

1. Extract RTO/RPO per workload from the business, not from engineering pride.
   "Zero downtime, zero loss" answers get costed first — they usually revise.
2. Map to the standard DR tiers (cost and complexity ascend):
   - **Backup & restore:** RTO hours–days, RPO = backup interval. Cheapest.
   - **Pilot light:** data replicated cross-region; minimal core (DB replica)
     running; compute built on demand. RTO tens of minutes–hours, RPO minutes.
   - **Warm standby:** scaled-down full copy running in region 2. RTO minutes,
     RPO seconds–minutes.
   - **Active-active multi-region:** both serve traffic; failover is traffic
     shift. RTO ~seconds–minutes, RPO ≈ replication lag. Most expensive; data
     layer becomes the hard problem.
3. Multi-AZ FIRST: it is the cheap insurance inside one region and is assumed
   by every tier above. Region-level DR is a separate, deliberate purchase.
4. Design the data path for the chosen tier: automated cross-region backups;
   read replicas promotable; or multi-master (DynamoDB global tables / Spanner
   / Cosmos DB multi-region) for active-active.
5. Failover routing: health-checked DNS (Route 53 / Cloud DNS / Traffic
   Manager) or global LB/Front Door.
6. **Test the failover on a schedule.** An untested DR plan is a document, not
   a capability — game days, restore drills, with measured RTO/RPO vs target.

## Worked Example

Order system: downtime costs ~RM50k/hour, business tolerates ≤15 min outage
(RTO) and ≤5 min data loss (RPO).

- Tier: backup/restore fails RTO; pilot light borderline; **warm standby**
  fits: full stack at minimal scale in region 2, async DB replication
  (replication lag ≈ RPO, must be monitored against the 5-min budget),
  health-checked DNS failover, runbook + quarterly drill.
- Mapping: AWS — RDS cross-region read replica, ASG min=1 in region 2,
  Route 53 failover records. GCP — Cloud SQL cross-region replica, MIG min=1,
  Cloud DNS routing policies. Azure — geo-replicated Azure SQL, VMSS min=1,
  Traffic Manager/Front Door priority routing.
- Arithmetic: warm standby ≈ 20–40% of prod cost for region 2 vs ~RM12.5k+
  exposure per 15-minute incident — justified if region incidents are a real
  risk for this business; priced honestly in the provider calculator.

## Interpretation

- The tier guarantees its RTO/RPO only if drills prove it — quote the MEASURED
  numbers, not the design numbers.
- Active-active is not "better warm standby": it changes the data architecture
  (conflict resolution, consistency) and the team's operational maturity bar.

## Red Flags

- DR designed but never failed over ("Schrödinger's standby").
- Backups never restored (a backup is only proven by its restore).
- RPO promised below the replication lag actually observed.
- Cross-region pair sharing one fate domain (same provider account, one
  IaC pipeline that can destroy both, same DNS operator error).
- Spending active-active money on a workload whose honest RTO is 4 hours.

## Limitations

This recipe covers infrastructure failure, not data CORRUPTION (a bad deploy
replicates to the standby faithfully — point-in-time recovery handles that),
and not provider-wide failure (multi-cloud DR is an order-of-magnitude cost
few workloads justify).
