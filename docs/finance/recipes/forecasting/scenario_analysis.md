# Scenario & Sensitivity Analysis (FP&A / FMVA)

## Intent

Replace a single false-precision forecast with a base/upside/downside range and
identify which assumptions actually move the outcome.

## Inputs Required

- A BASE-CASE model (ideally driver-based) with its key assumptions isolated as
  inputs.
- Plausible RANGES for the two or three assumptions that matter most.

## Method

1. **Sensitivity (one variable at a time):** flex each key assumption ±X% and
   record the output swing. Rank assumptions by impact → this is the tornado
   chart; the top bars are what to manage and monitor.
2. **Scenario (variables together):** define coherent worlds —
   - Downside: demand weak, costs up, slower collection — all at once.
   - Base: planning assumptions.
   - Upside: favorable but realistic.
   Scenarios shock variables JOINTLY (real life correlates them); sensitivity
   isolates one.
3. Report the OUTPUT RANGE and the probability/triggers for each scenario, not a
   point estimate.

## Worked Example

Base operating profit RM80k. Key assumptions: volume, price, input cost.

- Sensitivity: volume ±10% → profit ±RM30k (biggest bar); price ±5% → ±RM25k;
  input cost ±5% → ±RM15k. Volume and price dominate; manage those.
- Scenarios:
  - Downside (volume −10%, price −5%, cost +5%): profit ≈ **RM10k**
  - Base: **RM80k**
  - Upside (volume +10%, price +3%, cost −2%): profit ≈ **RM130k**
- Decision framing: "RM10k–RM130k, centered ~RM80k, driven mostly by volume and
  price" is honest; "RM80k" alone is false precision.

## Interpretation

- The tornado tells you what to MONITOR (the top bars) and what to HEDGE.
- A downside that breaches a covenant, runway, or buffer is the actionable
  output — it converts forecasting into risk management.

## Red Flags

- Scenarios that only flex one variable (real downturns hit several at once).
- An "upside" used to justify the plan while the downside is ignored.
- Sensitivity ranges so narrow they manufacture confidence.

## Limitations

Scenarios are bounded judgments, not the full space of outcomes; the real world
can exceed the downside. The value is structured humility about the forecast,
not a guarantee of the range.
