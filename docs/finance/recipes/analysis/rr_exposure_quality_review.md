# Restructured & Rolled-Over (R&R) Exposure Quality Review

## Intent

Determine how much of a restructured/rolled-over book is genuinely viable
versus evergreened, and what honest classification would do to provisions.

## Inputs Required

- TOTAL LOAN BOOK and R&R BALANCE (share of book).
- Per R&R exposure: RESTRUCTURE COUNT, date of last cash payment, CASH
  COLLECTED versus INTEREST ACCRUED since first restructure.
- Whether interest is CAPITALIZED into principal at renewal.
- Current PROVISION balance against the R&R book.

## Method

1. Compute the R&R ratio: R&R BALANCE / TOTAL BOOK. Trend it across periods —
   growth of the ratio is migration, not new business.
2. Segment the R&R book into three buckets:
   a. Viable: one restructure, cash payments ≥ accrued interest since.
   b. Fragile: paying something, but cash < accrued interest (negative
      amortization in cash terms).
   c. Evergreened: repeated rollovers, interest capitalized, little or no
      cash since first restructure.
3. Map buckets to staging: viable → Stage 2 with cure clock; fragile →
   Stage 2/3 boundary; evergreened → Stage 3 (credit-impaired).
4. Estimate the provision need per bucket (lifetime expected loss; for the
   evergreened bucket use a recovery-based estimate, not a payment-based one).
5. PROVISION SHORTFALL = required provisions − current provisions. This is
   the unrecognized loss sitting in reported equity and historical profits.

## Worked Example

Book 200, R&R 60% = 120. Collections analysis shows only 35% of contractual
inflows arrive on time across the book.

- If segmentation finds: viable 30, fragile 50, evergreened 40.
- Indicative lifetime-loss assumptions: viable 10%, fragile 35%, evergreened
  60% → required provisions = 3 + 17.5 + 24 = **44.5**.
- Current provisions of, say, 8 → provision shortfall ≈ **36.5**, versus
  reported annual profit of 14 (7% ROA × 200): nearly three years of reported
  earnings are unrecognized losses.

## Interpretation

- R&R above 20% of book is elevated; above 40% the institution is in workout
  mode whether it admits it or not. 60% means the lending model has failed
  for the current environment.
- Cash collected below accrued interest on the R&R book means the book is
  growing through capitalization: reported assets are inflating with losses.

## Red Flags

- Restructure approvals sitting with origination teams (target protection).
- "Current" status achieved by bullet rescheduling rather than payments.
- The same borrowers appearing in every renewal cycle.
- Provisions flat while the R&R ratio climbs.

## Limitations

Segmentation quality depends on borrower-level cash data. Where data is
missing, classify conservatively (fragile, not viable) and say so explicitly.
