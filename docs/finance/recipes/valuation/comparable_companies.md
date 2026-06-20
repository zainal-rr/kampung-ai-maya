# Comparable Companies (Trading Multiples)

## Intent

Value a company by what the market pays for similar listed companies — the
relative-valuation sanity check on any intrinsic DCF.

## Inputs Required

- A PEER SET of comparable listed companies (same sector, size band, growth,
  margin profile).
- For each peer: market cap, net debt (→ enterprise value), and the metric
  (EBITDA, EBIT, revenue, net income).
- The TARGET's same metric.

## Method

1. Build the peer set honestly — true comparables, not a flattering selection.
2. For each peer compute the multiple:
   - EV/EBITDA, EV/Sales (enterprise-level), or P/E, P/B (equity-level).
   - Match the multiple to the value type (EV multiples ↔ enterprise value).
3. Take the median (more robust than mean to outliers) and the inter-quartile
   range across peers.
4. Apply to the target's metric:
   Implied EV = Target EBITDA × peer median EV/EBITDA.
5. Bridge to equity: Equity value = Implied EV − Target net debt.
6. Report the range (quartiles), not a single multiple.

## Worked Example

Peers' EV/EBITDA: 8.0, 9.5, 10.0, 11.0, 12.5 → median **10.0**, IQR 9.5–11.0.
Target EBITDA 120, net debt 150.

- Implied EV = 120 × 10.0 = **1200** (range 1140–1320 at the quartiles)
- Equity value = 1200 − 150 = **1050** (range 990–1170)

Compare to the DCF example's equity value (~1180–1530): the DCF sits above the
comps range, so either the market is discounting something the DCF ignores, or
the DCF's growth/terminal assumptions are rich. That tension is the insight.

## Interpretation

- Median + IQR gives an honest band. A target valued above the peer top quartile
  needs a specific reason (faster growth, higher margin) — name it.
- EV/EBITDA neutralizes capital structure and is the default; P/E is distorted
  by leverage and one-offs.

## Red Flags

- A peer set chosen to hit a target number ("comp shopping").
- Mixing growth stages — a 30%-grower and a 3%-grower do not share a multiple.
- Using equity multiples (P/E) while ignoring different debt loads.

## Limitations

Relative valuation reprices the market's current mood; if the whole sector is
mispriced, comps inherit the error. Always pair with intrinsic
(`dcf_valuation.md`).
