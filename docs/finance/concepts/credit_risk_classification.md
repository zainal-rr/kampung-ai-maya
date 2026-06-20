# Credit Risk Classification

## Classification Ladder

- Performing: payments current, no signs of borrower distress.
- Watch / Special mention: early arrears (typically 30-89 days) or visible
  stress in the borrower's cash flows even if payments are current.
- Restructured & rolled-over (R&R): terms changed because the borrower could
  not meet the original schedule. A restructure granted due to financial
  difficulty is a *concession*, and the exposure does not return to clean
  performing status just because the new schedule is technically current.
- Non-performing (NPL): typically 90+ days past due, or unlikely-to-pay
  regardless of arrears.

## Staging Logic (IFRS 9 Style)

- Stage 1: performing, 12-month expected loss provisioning.
- Stage 2: significant increase in credit risk since origination — a
  restructure due to difficulty is strong evidence of this. Lifetime expected
  loss provisioning.
- Stage 3: credit-impaired — repeated restructures with weak collections,
  interest capitalization to avoid default, or unlikely-to-pay indicators.
- Cure periods matter: a restructured loan should demonstrate sustained
  payment performance (commonly 6-12 months of on-schedule cash payments)
  before upgrading. Rollover without cash collection restarts the clock.

## Evergreening

Evergreening is using new lending or rescheduling to keep a dead loan looking
alive. Indicators:

1. Interest capitalized into new principal at each renewal.
2. Bullet reschedules that push all principal to a future date repeatedly.
3. Collections on the restructured book persistently below accrued interest
   (the borrower cannot even service interest in cash).
4. Restructure decisions made by the same unit whose targets the loan affects.
5. R&R share of the book growing faster than the book itself.

## Non-Deposit Lender Specifics

A non-deposit financial institution has no central-bank liquidity backstop and
usually no deposit franchise to fall back on. Its funding is wholesale or
capital-markets based, so classification honesty matters *more*, not less: the
institution's own creditors read the same balance sheet, and discovering
understated R&R later destroys refinancing access exactly when it is needed.

## Provisioning Consequence

Moving 60% of a book to honest Stage 2/3 treatment typically raises lifetime
expected-loss provisions materially. If reported profits never absorbed that
charge, both capital and the historical ROA series are overstated.
