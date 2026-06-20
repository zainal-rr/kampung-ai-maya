# Risk Taxonomy (FRM Lens)

## The Four Core Risk Types

- **Market risk:** loss from moves in prices/rates — equity, interest rate,
  FX, commodity. Measured by sensitivity (duration, beta, delta) and by
  distribution (VaR, expected shortfall).
- **Credit risk:** loss from a counterparty failing to pay. Decomposed as
  Expected Loss = PD × LGD × EAD (probability of default × loss given default ×
  exposure at default). See `concepts/credit_risk_classification.md`.
- **Liquidity risk:** inability to meet obligations or sell assets without
  large loss. Two flavors: funding liquidity (can I pay?) and market liquidity
  (can I sell?). See `concepts/liquidity_risk.md`.
- **Operational risk:** loss from failed processes, people, systems, or
  external events. Hardest to quantify; managed by controls and scenario
  analysis, not just statistics.

## Measuring vs Managing

Measurement (VaR, duration, PD) tells you how much risk exists. Management
(limits, hedging, diversification, capital buffers) decides how much to keep.
A number without a limit is decoration; a limit without a number is a guess.

## Key Mental Models

- **VaR is a threshold, not a worst case.** "1-day 99% VaR of RM1m" means: on
  99 of 100 days, loss should not exceed RM1m. It says nothing about the
  severity of the 1-in-100 day — that is the tail, where **expected shortfall**
  (average loss beyond VaR) and stress testing live.
- **Normal-distribution VaR understates tails.** Real returns are fat-tailed;
  parametric VaR assuming normality routinely misses the crashes that matter.
- **Diversification reduces idiosyncratic risk, not systematic risk.** You can
  diversify away company-specific risk; you cannot diversify away the market.
- **Risk and uncertainty differ.** Risk has a knowable distribution;
  uncertainty does not. Stress testing exists precisely because the worst
  events are uncertain, not merely risky.

## The Honest Rule

Every risk number is conditional on a model and a data window. State the
confidence level, horizon, and assumptions. A VaR quoted without "1-day, 99%,
parametric/historical" is unusable.
