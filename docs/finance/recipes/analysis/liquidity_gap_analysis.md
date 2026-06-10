# Liquidity Gap Analysis

## Intent

Quantify whether an institution can meet near-term obligations from realistic
inflows, by time bucket, and compute the funding gap and coverage ratio.

## Inputs Required

- OBLIGATIONS by bucket: amounts due in 0-1m, 1-3m, 3-6m (debt service,
  operating costs, committed disbursements).
- CONTRACTUAL INFLOWS by bucket from the loan book and other receivables.
- ON-TIME COLLECTION RATE (cash received on schedule / contractually due).
- DELAY PROFILE for late collections (e.g. 90-150 days late).
- COUNTERBALANCING CAPACITY: unencumbered sellable assets, committed undrawn
  facilities, cash on hand.

## Method

1. Build the maturity ladder. Place every obligation and contractual inflow
   in its actual bucket. Never net across buckets.
2. Convert contractual inflows to expected inflows:
   EXPECTED INFLOW = CONTRACTUAL DUE × ON-TIME RATE.
   Shift the delayed remainder to the bucket implied by the delay profile and
   apply a further haircut (suggested 20-40%) for re-delay and loss.
3. Per-bucket gap: GAP = EXPECTED INFLOW − OBLIGATIONS.
4. Cumulative gap: running sum of bucket gaps. The first negative cumulative
   bucket is the survival boundary.
5. Coverage ratio: TOTAL EXPECTED INFLOWS / TOTAL OBLIGATIONS for the horizon.
6. Add counterbalancing capacity to the cumulative line to get the adjusted
   survival horizon.
7. Stress pass: rerun with the on-time rate cut by a third and asset sale
   values haircut by half.

## Worked Example

Institution with 60 due within 3 months; expected inflows 30 in the same
window (already behavior-adjusted); cash on hand included in the 30.

- Gap (0-3m) = 30 − 60 = **−30** (units: millions).
- Coverage ratio = 30 / 60 = **0.50**: only half of near-term obligations are
  funded by expected inflows.
- If the 30 of expected inflows itself derives from contractual due of ~86 at
  a 35% on-time rate, the delayed ~56 lands at 90-150 days — *after* the
  obligations fall due. Timing, not volume, is the killer.
- Stress: on-time rate 23% → expected inflows ~20 → gap −40.
- Survival boundary is inside the 3-month bucket unless counterbalancing
  capacity ≥ 30 exists today.

## Interpretation

- Coverage ≥ 1.0 per bucket: funded. 0.8-1.0: tight, needs standby lines.
- Below 0.7 in the 0-3m bucket: funding crisis now, not a forecast.
- A positive total gap with a negative near bucket is still a crisis: assets
  cannot be eaten in maturity order.

## Red Flags

- Gap analysis presented on contractual inflows when collections are weak.
- "Expected" inflows that quietly include hoped-for new fundraising.
- Counterbalancing capacity counted at book value instead of fire-sale value.
- Obligations excluding committed but undrawn project disbursements.

## Limitations

This is a point-in-time cash view. It does not capture covenant accelerations,
margin calls, or intra-month spikes; those need a daily 13-week cash forecast
(see `balance_sheet_survival_playbook.md`).
