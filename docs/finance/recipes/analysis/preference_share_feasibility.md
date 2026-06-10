# Redeemable Preference Share Issuance Feasibility

## Intent

Assess, from an investor's perspective, whether a proposed redeemable
preference share (RPS) raise is investable, and what it does to the issuer's
balance sheet risk.

## Inputs Required

- RAISE AMOUNT, proposed DIVIDEND RATE, REDEMPTION DATE/terms.
- USE OF PROCEEDS split: covering existing gaps versus new earning assets.
- Issuer cash generation: cash-adjusted income (see
  `roa_reliability_adjustment.md`) and the liquidity gap profile.
- Existing creditor structure and any covenants affected.

## Method

1. Classify the instrument honestly. Redeemable preference shares with a
   fixed redemption date behave like subordinated debt: they add a future
   refinancing obligation, not permanent capital.
2. Test dividend serviceability in cash:
   ANNUAL DIVIDEND = RAISE × DIVIDEND RATE; compare against cash-adjusted
   income, not reported income. Dividends are paid in cash, not accruals.
3. Test redemption serviceability: where does RAISE come from at redemption?
   If the answer is "refinance", the instrument moves the cliff, it does not
   remove it.
4. Examine use of proceeds: money plugging a liquidity gap created by
   non-collecting assets earns nothing; the dividend on it is pure drag.
5. Price the investor's risk: subordinated to all creditors, senior only to
   equity, in an issuer whose asset quality metrics (R&R share, collection
   rate) are public to any diligent investor. Estimate the required rate and
   compare with what the issuer can pay (step 2).
6. List the conditions a rational investor would demand: independently
   reviewed loan classification, board representation or observer rights,
   dividend step-ups, negative pledges, use-of-proceeds covenants, and
   information rights.

## Worked Example

Raise 100 at an assumed 10% dividend; issuer cash-adjusted income ≈ 4.6,
near-term liquidity gap 30, R&R 60% of book, collections 35% on time.

- Annual dividend = **10**, against cash-adjusted income of **4.6**: the
  issuer cannot service the coupon from real earnings, let alone build
  redemption reserves.
- 30 of the 100 immediately fills the existing gap (earns nothing); the
  remaining 70 goes into "project financing" through the same origination
  machine that produced 60% R&R.
- At redemption the issuer must find 100 from a book that collects 35% on
  time. Probability-weighted, the investor is funding a workout, not growth.
- Verdict shape: not investable on standard terms. Any real investor demands
  deep restructuring conditions first, or prices the instrument like
  distressed subordinated debt — which the issuer's cash flows cannot carry.

## Interpretation

- An instrument is feasible when cash income covers the dividend with margin
  (≥ 2x) and a credible redemption source exists that is not "refinance".
- Raising redeemable capital to cover gaps caused by asset quality is
  refinancing insolvency: it converts a credit problem into a bigger,
  dated funding problem.

## Red Flags

- Marketing the raise on reported ROA while collections data says otherwise.
- Proceeds "for growth" routed through unchanged underwriting.
- Redemption assumptions relying on the next raise.

## Limitations

Terms vary: perpetual or equity-convertible preference structures change the
analysis materially toward true capital. Reassess if redemption is removed.
