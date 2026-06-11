# Well-Architected Principles (The Shared Pillars)

All three providers publish a framework — AWS Well-Architected, the Google
Cloud Architecture Framework, and the Azure Well-Architected Framework — and
they converge on the same pillars. Designs should be reviewed against all of
them; most bad architectures over-serve one pillar and silently starve another.

## The Pillars

- **Operational excellence:** run and observe the workload; automate change;
  learn from failure. Tell: if deploys are manual or unmonitored, nothing else
  matters for long.
- **Security:** identity first, least privilege, encrypt in transit and at
  rest, defense in depth, audit everything. See `identity_and_access.md`.
- **Reliability:** survive component failure; design for the failure modes you
  expect (AZ loss, region loss, dependency outage). Measured by availability
  targets and RTO/RPO, not by hope.
- **Performance efficiency:** right resource types and sizes; scale
  horizontally; measure before optimizing.
- **Cost optimization:** pay for what the requirement needs, not what habit
  provisions. See `recipes/cost/cost_optimization_review.md`.
- **Sustainability (AWS) / operational continuity variants:** newer pillar;
  minimize wasted compute.

## The Shared Responsibility Model

The provider secures the cloud (hardware, facilities, hypervisor); the customer
secures what is IN the cloud (data, identity, network rules, OS patching —
the split moves with the service model). The higher the abstraction
(IaaS → PaaS → SaaS/serverless), the more the provider takes on. Most cloud
breaches are customer-side misconfigurations (open buckets, over-broad IAM),
not provider failures.

## Core Design Mental Models

- **Design for failure:** everything fails; the design question is what happens
  WHEN, not IF. Multi-AZ is the default, not the upgrade.
- **Stateless scales, state constrains:** push state to managed stores
  (databases, object storage, caches) so compute can scale horizontally and be
  replaced freely.
- **Managed-first:** prefer the managed service unless a hard requirement
  (cost at scale, portability, exotic config) forces self-managed. The
  operational burden you avoid is usually worth more than the premium.
- **Infrastructure as code:** if it isn't in code (Terraform, CloudFormation,
  Bicep), it isn't reproducible, reviewable, or recoverable.
- **Explicit trade-offs:** every pillar trades against cost. An honest design
  states what it does NOT protect against.
