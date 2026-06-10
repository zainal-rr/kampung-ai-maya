# Balance Sheet Survival Playbook (Stressed Lender)

## Intent

Sequence the immediate priorities and alternative strategies for a lender
facing a near-term liquidity gap driven by weak collections, so survival
actions come before capital-raising cosmetics.

## Inputs Required

- Liquidity gap profile by bucket (from `liquidity_gap_analysis.md`).
- R&R segmentation (from `rr_exposure_quality_review.md`).
- Funding map: every obligation, holder, maturity, covenant, and security.
- Disbursement pipeline: committed but undrawn lending.

## Method

1. Stop the bleed (day 1): freeze new disbursements and renewals that are
   not contractually committed. Every unit lent now is a unit unavailable
   for obligations due in 90 days.
2. Stand up a cash control tower (week 1): daily collections reporting, a
   rolling 13-week cash forecast, single owner with authority over all
   outflows above a threshold.
3. Triage the book (weeks 1-4): apply the R&R segmentation. Viable →
   tightened schedules with incentives for early cash; fragile → restructure
   once more only against new cash or collateral; evergreened → move to
   recovery/workout, stop accruing income.
4. Liability management (weeks 2-6): approach funders *before* default with
   the honest gap analysis and a credible collections plan; negotiated
   extensions cost covenants and pricing, surprise defaults cost the
   institution itself.
5. Monetize assets (parallel): sell or securitize the genuinely performing
   slice of the book; pledge unencumbered assets for a bridge facility.
   Fire-sale haircuts on the good book usually beat default on obligations.
6. Fix the engine before refueling: underwriting, collections capacity, and
   classification integrity must be demonstrably repaired before any capital
   raise — otherwise new money exits through the same hole.
7. Raise capital last, and prefer true loss-absorbing instruments (equity,
   perpetual/convertible structures) over dated redeemable instruments that
   re-create the cliff (see `preference_share_feasibility.md`).

## Worked Example

Gap of 30 due inside 3 months, expected inflows 30, book 200 with 40%
performing cleanly (≈80).

- Freezing 20 of planned new disbursements closes two-thirds of the gap.
- Selling or repo-financing 25-35 of the performing book at a 10-15% haircut
  covers the remainder and buys two quarters.
- A negotiated 6-month extension on 20 of the 60 due converts the cliff into
  a ledge. Combined, survival horizon extends past 12 months without any new
  capital — which is when a raise becomes negotiable on sane terms.

## Interpretation

- Order matters: actions that need nobody's permission (freeze, control
  tower, triage) come before actions that need counterparties (extensions,
  sales) which come before actions that need believers (capital).
- A raise executed before the engine is fixed buys quarters, not survival.

## Red Flags

- "Growth" disbursements continuing during a liquidity crisis.
- Cash forecasts owned by the team whose performance they measure.
- Asset sales rejected because book-value losses would crystallize — the
  loss already exists; refusing to crystallize it forfeits the liquidity.

## Limitations

Jurisdiction-specific insolvency, regulatory, and contract law constrain
every step here; local counsel review is part of execution, not optional.
