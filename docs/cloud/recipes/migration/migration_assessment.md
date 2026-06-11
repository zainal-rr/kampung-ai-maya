# Cloud Migration Assessment (The 6 Rs)

## Intent

Decide, application by application, HOW each workload should move to the cloud
(or not move at all) — producing a portfolio disposition, not a slogan.

## Inputs Required

- APPLICATION INVENTORY: what runs, on what, owned by whom, business criticality.
- DEPENDENCIES: app-to-app and app-to-data couplings (the migration order driver).
- LICENSE constraints (databases and enterprise software change the math).
- DRIVERS: why migrate — datacenter exit deadline, cost, agility, compliance?
- Team CAPACITY for re-engineering vs just moving.

## Method

1. Inventory and dependency-map first; group apps into MOVE GROUPS that must
   travel together.
2. Assign each app one of the 6 Rs:
   - **Rehost** ("lift and shift"): move VMs as-is. Fastest, least benefit;
     right under deadline pressure.
   - **Replatform** ("lift and reshape"): minor swaps on the way — self-run DB
     → managed DB, VM → container. The pragmatic middle.
   - **Refactor/Re-architect:** rebuild for cloud-native (serverless,
     microservices). Highest cost and payoff; reserve for the workloads where
     agility/scale is the actual business driver.
   - **Repurchase:** drop the custom app for SaaS (CRM, HR, email almost always).
   - **Retire:** kill it. A real assessment finds a meaningful share of the
     portfolio nobody still needs.
   - **Retain:** stays put for now (latency to a factory floor, compliance,
     end-of-life soon, mainframe gravity).
3. Sequence: start with a low-risk, visible pilot from the rehost/replatform
   pile; leave the refactors until the team has cloud operating experience.
4. Land everything inside the landing zone (`architecture/landing_zone_design.md`)
   — migrating into an ungoverned account recreates the old mess with a
   monthly bill.
5. Define per-app success criteria (performance parity, cost target, cutover
   window) and a rollback plan for each cutover.

## Worked Example

Datacenter exit in 12 months, 40 applications.

- Disposition after assessment: retire 6 (15%), repurchase 4 (email, HR,
  CRM, ITSM), retain 3 (factory-adjacent, latency-bound), rehost 18,
  replatform 7 (databases → managed), refactor 2 (the customer-facing revenue
  apps where scale actually matters).
- Sequencing: pilot = one internal rehost app, month 1–2; waves of move
  groups monthly; refactors run as parallel product work, not on the exit
  critical path — the deadline is met by rehost, not by rebuilding.
- Tooling mapping: AWS Application Migration Service / Migration Hub; GCP
  Migrate to Virtual Machines / Migration Center; Azure Migrate. Database
  moves via DMS / Database Migration Service / Azure DMS.

## Interpretation

- The portfolio mix IS the strategy: a deadline-driven exit skews rehost
  (speed), a cost-driven one skews replatform+retire, an innovation-driven one
  funds the few refactors that matter.
- Rehosted apps inherit none of cloud's elasticity — flag them for a
  post-migration optimization pass (`cost/cost_optimization_review.md`), or
  the cloud bill will exceed the datacenter it replaced.

## Red Flags

- "Refactor everything" plans against a fixed deadline — they miss it.
- No retire/repurchase pass (paying to move things nobody uses).
- Dependencies discovered DURING cutover (the inventory was wishful).
- Like-for-like sizing copied from on-prem peaks → instant overprovisioning.
- No rollback plan per cutover window.

## Limitations

The 6-R label is a decision aid, not a contract — apps shift buckets as
discovery deepens. License and egress economics need provider-current numbers.
Organizational readiness (operating model, skills) gates everything and is
outside this recipe's scope.
