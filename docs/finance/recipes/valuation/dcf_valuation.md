# Discounted Cash Flow (DCF) Valuation

## Intent

Value a business on its own fundamentals by projecting free cash flow and
discounting it to present value (the FMVA/CFA intrinsic-value workhorse).

## Inputs Required

- Revenue and its growth, operating margin (→ EBIT), tax rate.
- Depreciation/amortization, capital expenditure, change in working capital.
- WACC (discount rate), terminal growth rate or exit multiple.
- Net debt (to bridge enterprise value to equity value).

## Method

1. Project unlevered free cash flow to firm (FCFF) per year:
   FCFF = EBIT × (1 − tax) + D&A − Capex − Δ Working capital
2. Discount each year: PV = FCFF_t / (1 + WACC)^t
3. Terminal value (perpetuity growth):
   TV = FCFF_(n+1) / (WACC − g), then discount TV back from year n.
   (Or exit multiple: TV = EBITDA_n × multiple.)
4. Enterprise value = Σ PV(FCFF) + PV(TV)
5. Equity value = Enterprise value − Net debt; per share = Equity value / shares.
6. Build a sensitivity table on WACC and g — the output is a RANGE.

## Worked Example

Year-1 FCFF 100, growing 8% for 5 years; WACC 10%; terminal growth 3%; net debt 150.

- FCFF: 100, 108, 116.6, 126.0, 136.0
- PV each (÷1.10^t): 90.9, 89.3, 87.6, 86.0, 84.5 → Σ = **438.3**
- TV = FCFF_6 / (WACC−g) = (136.0×1.03)/(0.10−0.03) = 140.1/0.07 = **2001**
- PV of TV = 2001 / 1.10^5 = **1242**
- Enterprise value = 438 + 1242 = **1680**; Equity value = 1680 − 150 = **1530**
- Note: terminal value is 74% of EV — typical, and the reason g and WACC
  dominate. At WACC 11% / g 2.5%, equity value falls to ~**1180** (−23%).

## Interpretation

- Quote the RANGE from the sensitivity table, never the point. A DCF that
  reports one number is hiding its own fragility.
- If terminal value is >80% of EV, the explicit forecast barely matters — the
  valuation is really a bet on the perpetuity assumption; flag it.
- Cross-check against relative valuation (`comparable_companies.md`). Big
  divergence means one of them is wrong; find out which.

## Red Flags

- Terminal growth above long-run GDP/inflation (a firm cannot outgrow the
  economy forever).
- WACC that doesn't reflect the firm's actual risk/leverage.
- Hockey-stick revenue with no margin cost — growth without investment is fiction.

## Limitations

Garbage in, garbage out: a DCF is only as good as its assumptions, and small
WACC/g changes swing it widely. Use for fundamentals-driven names with
predictable cash flows; it is weak for pre-revenue, cyclical-peak, or
distressed situations.
