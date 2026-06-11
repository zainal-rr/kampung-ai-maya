# Financial Statement Ratio Analysis

## Intent

Read a company's health from its statements using the four ratio families, and
interpret them against thresholds and peers rather than in isolation.

## Inputs Required

- INCOME STATEMENT: revenue, COGS, operating income (EBIT), interest, net income.
- BALANCE SHEET: current assets, inventory, current liabilities, total assets,
  total debt, equity.
- Optionally PEER or PRIOR-PERIOD figures for comparison (ratios are relative).

## Method

1. **Liquidity** (can it pay short-term bills?):
   - Current ratio = Current assets / Current liabilities
   - Quick ratio = (Current assets − Inventory) / Current liabilities
2. **Profitability** (does it earn?):
   - Gross margin = Gross profit / Revenue
   - Operating margin = EBIT / Revenue
   - Net margin = Net income / Revenue
   - ROE = Net income / Equity; ROA = Net income / Total assets
3. **Leverage / solvency** (can it survive its debt?):
   - Debt-to-equity = Total debt / Equity
   - Interest coverage = EBIT / Interest expense
4. **Efficiency** (how hard do assets work?):
   - Asset turnover = Revenue / Total assets
   - Inventory turnover = COGS / Inventory; Receivables days = AR / Revenue × 365
5. Trend each ratio over 3+ periods and compare to peers. A ratio is a question,
   not an answer — direction and context matter more than the level.

## Worked Example

Revenue 500, COGS 300, EBIT 80, interest 20, net income 45. Current assets 200
(inventory 90), current liabilities 120. Total assets 600, debt 250, equity 220.

- Current ratio = 200/120 = **1.67**; Quick = (200−90)/120 = **0.92**
- Gross margin = 200/500 = **40%**; Operating = 80/500 = **16%**; Net = 45/500 = **9%**
- ROE = 45/220 = **20.5%**; ROA = 45/600 = **7.5%**
- Debt-to-equity = 250/220 = **1.14**; Interest coverage = 80/20 = **4.0x**
- Asset turnover = 500/600 = **0.83x**

## Interpretation

- Current ratio > 1.5 generally comfortable; quick < 1.0 means it leans on
  inventory to cover short-term bills — watch if inventory is slow-moving.
- Interest coverage < 2x is fragile; < 1x means operating profit cannot service
  debt. 4x here is adequate, not strong.
- ROE looks healthy at 20.5% — but decompose it (see
  `dupont_decomposition.md`) before trusting it; high ROE driven by leverage is
  not the same as high ROE driven by margins.

## Red Flags

- Margins fine but cash flow weak → earnings quality problem (`cash_flow_quality.md`).
- Rising receivables days → revenue booked faster than collected.
- ROE rising only because equity is shrinking (buybacks/losses), not income up.

## Limitations

Ratios are accounting-based and gameable; they compare only against the right
peer set and consistent accounting policies. They diagnose, they do not value —
for value use `recipes/valuation/`.
