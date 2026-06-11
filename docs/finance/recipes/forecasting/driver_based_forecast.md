# Driver-Based Forecasting (FP&A / FMVA)

## Intent

Build a forecast from operational DRIVERS (units, price, headcount, conversion)
rather than blanket growth rates, so the numbers are explainable and the
assumptions are testable.

## Inputs Required

- The revenue/cost DRIVERS that actually move the business (volume × price,
  customers × ARPU, headcount × productivity).
- Historical values for each driver and their realistic trajectory.
- Fixed vs variable cost split.

## Method

1. Decompose revenue into drivers: Revenue = Volume × Price (or Customers ×
   ARPU × retention, etc.). Never forecast "revenue grows 10%"; forecast the
   drivers that produce the 10%.
2. Forecast each driver explicitly with a stated rationale (capacity, pipeline,
   seasonality, market size).
3. Model costs by behavior: variable costs scale with the volume driver; fixed
   costs step with capacity decisions, not with revenue.
4. Roll up to revenue, gross margin, operating income.
5. Keep a **rolling forecast** (re-forecast each period on actuals) rather than
   a once-a-year static budget.

## Worked Example

SaaS: 1,000 customers, ARPU RM200/mo, monthly churn 3%, adding 80 net new/mo.

- Month-1 customers = 1,000 × (1−0.03) + 80 = **1,050**
- Month-1 revenue = 1,050 × 200 = **RM210,000**
- Drivers to defend: is 80 net-new sustainable given pipeline? Is 3% churn
  improving or worsening? Each is a falsifiable assumption a reviewer can challenge.
- A naive "revenue +5%/mo" hides all of that and breaks the moment churn moves.

## Interpretation

- Driver-based forecasts fail LOUDLY and traceably — when actuals miss, you see
  WHICH driver (churn up? net-new down?), which is the whole point.
- Tie every forecast line to a driver and an owner. An unowned assumption is a
  guess.

## Red Flags

- Top-line percentage growth with no operational basis ("hockey stick").
- Variable costs modeled as a flat percent forever, ignoring scale or step costs.
- A static annual budget never revisited — stale by Q2.

## Limitations

A forecast is a structured opinion, not a prediction. Driver clarity improves
explainability and revision, not certainty; always pair with scenario analysis
(`scenario_analysis.md`).
