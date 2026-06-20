# Valuation Principles

## Two Families

- **Intrinsic (absolute):** value from the asset's own cash flows, discounted
  for time and risk. Discounted cash flow (DCF) is the archetype. Answers "what
  is this worth on its fundamentals?"
- **Relative (market):** value by comparison — trading multiples of comparable
  companies, or precedent-transaction multiples. Answers "what is the market
  paying for similar assets?"

A disciplined valuation triangulates both. Intrinsic without a market sanity
check drifts; relative without intrinsic just reprices the herd.

## Time Value Of Money (the spine of intrinsic value)

A ringgit today is worth more than a ringgit next year, because today's can be
invested. Present value: PV = FV / (1 + r)^n. Everything in DCF is this idea
applied to a stream of future cash flows.

## The Discount Rate

- For whole-firm (enterprise) DCF: WACC — the blended after-tax cost of debt
  and cost of equity, weighted by capital structure.
- For equity-only DCF: cost of equity, usually from CAPM
  (`concepts/portfolio_theory.md`).
- The discount rate encodes risk. Higher risk → higher rate → lower value.
  Small changes move valuations a lot; always show the sensitivity.

## Enterprise vs Equity Value

- **Enterprise value (EV):** value of the whole business (all capital
  providers). DCF of free cash flow to firm, discounted at WACC.
- **Equity value:** EV − net debt. What shareholders own.
- Multiples must match: EV/EBITDA and EV/Sales pair with enterprise value;
  P/E and P/B pair with equity value. Mixing them is a classic error.

## Terminal Value

Most of a DCF's value usually sits in the terminal value (cash flows beyond the
explicit forecast). Two methods: perpetuity growth (Gordon) or exit multiple.
Because it dominates, terminal-value assumptions deserve the most scrutiny — a
0.5% change in perpetual growth can swing the answer 15%+.

## The Honest Rule

A valuation is a model of assumptions, not a fact. Always present a range from a
sensitivity table, name the two or three assumptions that drive it, and never
quote a single-point value as if it were observed.
