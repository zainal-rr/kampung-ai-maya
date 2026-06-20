# Liquidity Risk

## The Maturity Ladder

Liquidity analysis is done in time buckets, not totals. Standard buckets:
0-1 month, 1-3 months, 3-6 months, 6-12 months, over 12 months. Obligations
and inflows are placed in the bucket where they *actually* fall due or arrive,
and gaps are computed per bucket and cumulatively. A institution can be
solvent on paper and dead in the 0-3 month bucket.

## Contractual Versus Behavioral Inflows

Contractual inflows are what the loan agreements say arrives. Behavioral
inflows are what experience says arrives. The adjustment:

- EXPECTED INFLOW(bucket) = CONTRACTUAL DUE × ON-TIME RATE
- The delayed remainder shifts to later buckets with a further haircut for
  re-delay and outright loss, never assumed to arrive in full.

Using contractual inflows in a gap analysis when collections run at 35%
on-time is not optimism, it is misstatement.

## Survival Horizon

The number of days the institution can meet obligations using expected
inflows plus counterbalancing capacity (unencumbered assets that can be sold
or pledged, committed undrawn lines). Survival horizon under stress is the
single most decision-relevant liquidity number for a wholesale-funded lender.

## Funding Concentration

Wholesale-funded institutions fail through refinancing, not through deposit
runs. Key checks: share of funding maturing within 3 months, largest single
funder share, covenant triggers that accelerate obligations, and whether any
new instrument (including redeemable preference shares) merely moves the
refinancing cliff rather than removing it.

## Stress Factors In A War-Affected Economy

- Supply shocks (fuel, transport) lengthen borrower cash cycles: assume
  collection rates fall further, not that they mean-revert.
- Collateral becomes illiquid exactly when it is needed.
- Currency and payment-system disruption can trap inflows that were "on time".
- Lender-of-last-resort support for non-deposit institutions is usually
  unavailable; plan as if no external rescue exists.
