# Portfolio Performance Metrics

## Intent

Judge an investment portfolio on RISK-ADJUSTED return, not headline return — the
CFA discipline of separating skill from luck and from leverage.

## Inputs Required

- Portfolio returns over a series of periods (and the period count).
- Risk-free rate (Rf) for the same period.
- Benchmark/market return (Rm) and the portfolio's beta, for alpha/CAPM.

## Method

1. **Return:** annualize the periodic return consistently (geometric, not
   arithmetic, for compounding: (Π(1+r))^(1/n) − 1).
2. **Volatility:** standard deviation of periodic returns, annualized
   (× √periods-per-year).
3. **Sharpe ratio** = (Portfolio return − Rf) / Volatility. Return per unit of
   total risk.
4. **CAPM expected return** = Rf + β(Rm − Rf).
5. **Alpha** = Actual return − CAPM expected return. Skill after adjusting for
   market exposure.
6. Compare Sharpe and alpha across portfolios and against the benchmark.

## Worked Example

Portfolio return 14%, Rf 3%, volatility 12%, β 1.2, market return 9%.

- Sharpe = (14 − 3) / 12 = **0.92**
- CAPM expected = 3 + 1.2 × (9 − 3) = 3 + 7.2 = **10.2%**
- Alpha = 14 − 10.2 = **+3.8%**

The portfolio beat the market (14% vs 9%) — but it also took more market risk
(β 1.2). After adjusting, it still added 3.8% of genuine alpha and earned 0.92
of return per unit of risk. That is a real result, not just a leveraged one.

## Interpretation

- Sharpe > 1 is good, > 2 excellent (and rare/suspect over short windows).
- Positive alpha = outperformance attributable to selection/timing, not just
  riding a high beta in a bull market.
- A high raw return with negative alpha means the manager added risk, not value.

## Red Flags

- Sharpe computed over a short bull-market window (survivorship/luck).
- Alpha that vanishes once you use the right benchmark — wrong benchmark inflates skill.
- Volatility understated by illiquid, infrequently-priced holdings (common in
  alternatives — see `private_equity_returns.md`).

## Limitations

All of these assume a return distribution and a stable benchmark. They are
backward-looking; past Sharpe/alpha do not guarantee future performance, and
short series are statistically meaningless.
