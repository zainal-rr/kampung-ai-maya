# Budget Variance Analysis (FP&A)

## Intent

Explain WHY actuals differed from budget by decomposing the variance into its
causes, so the analysis drives a decision rather than just reporting a number.

## Inputs Required

- BUDGET (or forecast) and ACTUAL for each line, same period.
- Where possible, the volume/price/rate split behind each line.

## Method

1. Total variance per line = Actual − Budget. Tag favorable (F) or unfavorable
   (U) by impact on profit (higher revenue = F; higher cost = U).
2. Decompose revenue variance:
   - **Price variance** = (Actual price − Budget price) × Actual volume
   - **Volume variance** = (Actual volume − Budget volume) × Budget price
3. Decompose cost variance similarly into RATE and USAGE/efficiency components.
4. Rank variances by size; explain the top few with a cause and an action.
   A variance report without causes and actions is bookkeeping, not analysis.

## Worked Example

Budget: 1,000 units × RM50 = RM50,000. Actual: 1,100 units × RM48 = RM52,800.

- Total revenue variance = 52,800 − 50,000 = **+RM2,800 (F)**
- Price variance = (48 − 50) × 1,100 = **−RM2,200 (U)** (discounted to sell more)
- Volume variance = (1,100 − 1,000) × 50 = **+RM5,000 (F)**
- Check: −2,200 + 5,000 = +2,800 ✓
- Story: the favorable total HIDES a price cut. Volume bought the beat at the
  cost of margin — a decision worth questioning, invisible in the +2,800 headline.

## Interpretation

- A favorable total variance can mask an unfavorable driver (here, price). The
  decomposition is the entire value — never stop at the net number.
- Distinguish controllable variances (pricing, efficiency) from uncontrollable
  (FX, input prices) so accountability lands correctly.

## Red Flags

- Reporting only net variances (hides offsetting price/volume effects).
- "Timing" used to wave away every miss without proof it reverses next period.
- No action attached — variance analysis exists to change a decision.

## Limitations

Variance analysis explains the past against a budget that may itself have been
wrong; a clean variance against a bad budget is not success. Pair with
re-forecasting (`driver_based_forecast.md`).
