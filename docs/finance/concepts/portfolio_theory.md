# Portfolio Theory (CFA Lens)

## Return And Risk

- **Return:** for a single asset, the percentage gain over a period; for a
  portfolio, the weighted average of asset returns.
- **Risk:** standard deviation of returns (volatility). Portfolio risk is NOT
  the weighted average of asset risks — it depends on correlations, which is
  why diversification works.

## Diversification

Combining assets that do not move together reduces portfolio volatility below
the weighted average of the parts. The benefit grows as correlation falls. At
correlation = 1, no benefit; at correlation < 1, real benefit; at negative
correlation, strong hedging.

## Systematic vs Idiosyncratic Risk

- **Idiosyncratic (specific) risk:** company/asset-specific. Diversifiable —
  it washes out in a broad portfolio.
- **Systematic (market) risk:** affects everything. Not diversifiable. This is
  the risk the market pays you to bear, and it is what **beta** measures.

## CAPM (the cost-of-equity workhorse)

Expected return = Rf + β × (Rm − Rf)
- Rf = risk-free rate
- β = sensitivity to the market (1.0 = moves with market; >1 amplifies)
- (Rm − Rf) = equity risk premium

CAPM gives the required return for an asset's systematic risk, and is the usual
source of the cost of equity in valuation.

## Risk-Adjusted Performance

- **Sharpe ratio** = (Return − Rf) / Standard deviation. Return per unit of
  total risk. Higher is better; lets you compare portfolios of different risk.
- **Alpha** = actual return − CAPM-expected return. Excess return after
  adjusting for market exposure; the measure of skill (or luck).
- **Beta** = systematic-risk exposure (see CAPM).

## The Honest Rule

These metrics assume a return distribution and a chosen benchmark and window.
Sharpe on 3 months of a bull market is noise. Always state the period, the
risk-free proxy, and the benchmark, and prefer multi-period evidence.
