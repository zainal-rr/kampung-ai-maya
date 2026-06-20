# Value at Risk (VaR) and Expected Shortfall (FRM)

## Intent

Quantify the loss a portfolio could face over a horizon at a confidence level,
and — critically — what lies beyond that threshold.

## Inputs Required

- Portfolio VALUE and its return VOLATILITY (σ), or a HISTORICAL return series.
- CONFIDENCE level (95% or 99%) and HORIZON (1-day, 10-day).
- For non-normal tails: the full historical/simulated loss distribution.

## Method

1. **Parametric (variance-covariance) VaR** (assumes normal returns):
   VaR = Portfolio value × z × σ × √horizon
   where z = 1.65 (95%) or 2.33 (99%).
2. **Historical VaR:** rank actual historical losses; the VaR is the loss at the
   (1 − confidence) percentile. No normality assumption.
3. **Monte Carlo VaR:** simulate many return paths from a model; read the percentile.
4. **Expected shortfall (ES / CVaR):** the AVERAGE loss in the tail BEYOND VaR.
   This is what VaR hides and what actually hurts.

## Worked Example

Portfolio value RM10m, daily σ = 2%, 99% 1-day VaR, parametric.

- VaR = 10,000,000 × 2.33 × 0.02 × √1 = **RM466,000**
- Reading: on ~99 of 100 days, 1-day loss should not exceed RM466k.
- 10-day VaR = 466k × √10 = **RM1.47m** (time scaling by √horizon).
- Expected shortfall (99%) ≈ σ × value × φ(z)/(1−c) ≈ 10m × 0.02 × 2.665 =
  **RM533k** — the average loss ON a breach day exceeds the VaR itself.

## Interpretation

- VaR is a THRESHOLD, not a worst case. "RM466k 99% VaR" says nothing about how
  bad the 1-in-100 day is — that's expected shortfall's job, and ES is always
  worse than VaR.
- 99% VaR breached more than ~2–3 days in 100 (backtesting) means the model
  understates risk — usually the normality assumption failing on fat tails.

## Red Flags

- Parametric VaR on assets with fat tails or optionality (it badly understates).
- Quoting VaR without the confidence level and horizon — it is then meaningless.
- Treating VaR as a maximum loss. 2008 and 2020 lived entirely in the tail VaR
  ignores; that is why stress testing (`stress_testing.md`) is mandatory, not
  optional.

## Limitations

VaR is conditional on the model, the data window, and the distribution
assumption. It is silent on the tail, procyclical (low in calm markets, exactly
when risk builds), and must always be paired with expected shortfall and stress
scenarios.
