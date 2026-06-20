# Private Equity & Alternatives Returns (CAIA)

## Intent

Measure returns on illiquid, drawdown-style investments (PE, VC, real assets)
where public-market metrics mislead — using IRR, MOIC, and the J-curve.

## Inputs Required

- DATED CASH FLOWS: capital calls (negative) and distributions (positive),
  each with its date.
- Current NAV (residual value of unrealized holdings).
- For benchmarking: a public-market index series (for PME).

## Method

1. **MOIC (multiple on invested capital)** = (Total distributions + NAV) /
   Total capital called. "How many times my money back." Ignores time.
2. **IRR (internal rate of return)** = the discount rate that sets the NPV of
   all dated cash flows (calls, distributions, NAV) to zero. Time-weighted by
   construction; solved numerically. "What annualized rate did the timing earn."
3. **TVPI / DPI / RVPI:** Total/Distributed/Residual value to paid-in —
   realized vs unrealized split of the multiple.
4. **PME (public market equivalent):** compare the fund's cash flows to the same
   cash flows invested in a public index — did the illiquidity pay off?

## Worked Example

Year 0 call −100; Year 1 call −50; Year 3 distribution +40; Year 5 distribution
+200; current NAV 30.

- Total called = 150; Total distributed = 240; NAV = 30
- MOIC = (240 + 30) / 150 = **1.80x**
- IRR ≈ rate solving −100 −50/(1+r) +40/(1+r)^3 +230/(1+r)^5 = 0 → **≈ 19%**
- DPI = 240/150 = **1.60x** (realized); RVPI = 30/150 = 0.20x; TVPI = 1.80x.
- So most of the multiple is realized cash (good); 0.20x still rides on NAV marks.

## Interpretation

- MOIC and IRR answer different questions: a 2.0x MOIC over 10 years (IRR ~7%)
  is worse than a 1.5x over 3 years (IRR ~14%). Always quote both.
- DPI > 1.0 means the fund has returned more cash than was put in — real money,
  not marks. Early in a fund's life DPI is low and IRR is negative: the J-curve.
- **The J-curve:** fees and early calls make returns negative for the first 2–4
  years before distributions arrive. Judging a young fund on IRR is premature.

## Red Flags

- IRR flattered by early small distributions (IRR over-weights early cash) or by
  subscription-credit-line timing tricks — check DPI alongside.
- NAV-heavy returns (low DPI, high RVPI) — the gain is in self-reported marks,
  not realized cash. Discount accordingly.
- No PME — absolute IRR without a public benchmark hides whether illiquidity
  was rewarded at all.

## Limitations

NAV marks are manager-estimated and stale; IRR assumes reinvestment at the IRR
(often unrealistic). These metrics are only as honest as the valuation policy
behind the NAV.
