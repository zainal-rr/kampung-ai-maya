# ROA Reliability Adjustment (Cash-Adjusted Earnings)

## Intent

Test whether a reported return on assets is real by stripping uncollected
accruals and unrecognized provisioning out of reported income.

## Inputs Required

- REPORTED NET INCOME and AVERAGE TOTAL ASSETS (reported ROA = income/assets).
- R&R BALANCE and average YIELD on the book.
- CASH COLLECTION RATE (on-time cash / contractual due).
- PROVISION SHORTFALL from the R&R quality review (if available).

## Method

1. Reported ROA = NET INCOME / AVERAGE ASSETS.
2. Estimate uncollected accrued income:
   UNCOLLECTED ACCRUAL ≈ R&R BALANCE × YIELD × (1 − COLLECTION RATE).
   This is income recognized on exposures that did not pay in cash.
3. Cash-adjusted income = NET INCOME − UNCOLLECTED ACCRUAL.
4. Fully adjusted income = cash-adjusted income − (PROVISION SHORTFALL
   amortized over the period it accumulated, or charged in full for a
   point-in-time solvency view).
5. Cash-adjusted ROA = cash-adjusted income / AVERAGE ASSETS. Compare the
   three numbers: reported, cash-adjusted, fully adjusted.
6. Earnings quality ratio = CASH INCOME / ACCRUAL INCOME for the same period.

## Worked Example

Assets 200, reported ROA 7% → reported income 14. R&R book 120 at an
indicative 12% yield, on-time collection 35%.

- UNCOLLECTED ACCRUAL ≈ 120 × 0.12 × (1 − 0.35) = **9.4**.
- Cash-adjusted income = 14 − 9.4 = **4.6** → cash-adjusted ROA ≈ **2.3%**.
- Charge even a third of a 36.5 provision shortfall (≈12.2) and fully
  adjusted income is **−7.6** → adjusted ROA ≈ **−3.8%**.
- Conclusion shape: the institution's 7% is an accrual artifact; on a cash
  and credit-honest basis it is at best marginally profitable and plausibly
  loss-making.

## Interpretation

- Reported ROA stable while cash-adjusted ROA falls: deterioration is being
  capitalized into the loan book.
- Cash-adjusted ROA below the institution's funding cost means every period
  of operation destroys value even before credit losses.
- Earnings quality ratio < 0.6 alongside R&R > 40%: treat all profitability
  metrics as unreliable until restated.

## Red Flags

- Yield assumptions backed out of income rather than contract data.
- Income from restructuring fees booked upfront on loans that pay nothing.
- "One-off" recoveries recurring every period to plug the income line.

## Limitations

The uncollected-accrual estimate is a first-order approximation; it assumes
uniform yield and collection behavior across the R&R book. Borrower-level
data refines it but rarely changes the direction of the conclusion.
