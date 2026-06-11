# Stress Testing & Scenario Risk (FRM)

## Intent

Estimate losses under specific severe-but-plausible scenarios that statistical
risk measures (VaR) systematically miss, because the worst events live in the
tail VaR ignores.

## Inputs Required

- Portfolio EXPOSURES by risk factor (rates, FX, equity, credit spread, key
  counterparties).
- SCENARIO definitions: factor shocks (e.g. rates +200bp, equities −30%, FX
  −15%, a named counterparty default).
- SENSITIVITIES (duration, beta, delta) or full revaluation capability.

## Method

1. Choose scenarios in two families:
   - **Historical:** replay real crises (2008 GFC, 2020 COVID shock, a local
     currency crisis) on today's book.
   - **Hypothetical:** construct plausible forward shocks tied to current
     vulnerabilities.
2. For each scenario, revalue the portfolio (full revaluation preferred;
   sensitivity-based approximation if not): Loss = Σ exposure × factor shock.
3. Add **reverse stress testing:** start from "what loss would break us?" and
   find the scenario that produces it. This surfaces hidden fragilities.
4. Compare each scenario loss against capital/liquidity buffers and limits.

## Worked Example

Book: RM10m equities (β 1.1), RM5m bonds (duration 6), RM3m FX exposure.
Scenario "risk-off": equities −25%, rates +150bp, FX −10%.

- Equity loss = 10m × 1.1 × −0.25 = **−RM2.75m**
- Bond loss = 5m × −6 × 0.015 = **−RM0.45m** (price falls as rates rise)
- FX loss = 3m × −0.10 = **−RM0.30m**
- Total scenario loss = **−RM3.5m** — far above the RM0.47m 99% 1-day VaR.
That gap IS the point: VaR sized the normal day; the stress sized the bad one.

## Interpretation

- A stress loss that exceeds your capital/liquidity buffer is an actionable
  finding — hedge, reduce, or raise the buffer before the scenario arrives.
- Reverse stress that reaches a breaking point with a *plausible* scenario means
  the book is too fragile, regardless of what VaR says.

## Red Flags

- Stress scenarios so mild they never bind — theater, not risk management.
- Ignoring correlation breakdown: in crises, diversification fails and
  everything falls together; scenarios must shock factors jointly, not in isolation.
- No liquidity dimension — a solvent book that cannot fund the loss still dies
  (see `concepts/liquidity_risk.md`).

## Limitations

Scenarios are judgments; the next crisis rarely matches the last. Stress testing
bounds known vulnerabilities, not unknown ones — it complements VaR, it does not
replace judgment.
