# Excel Artifact Quality

## Maya Activation Wrapper
Active artifact quality skill. Progress is tracked only in `KAMPUNG_AI_CHECKLIST.md`.

## Purpose
Keep Maya-created `.xlsx` files practical, editable, and useful from both iMac and Telegram.

## Trigger Phrases
trigger: create, make, draft, review, or repair an Excel file, `.xlsx`, spreadsheet, tracker, budget, comparison sheet, workbook, template, or planner.
non-trigger: normal chat, Word-only requests, PowerPoint-only requests, HTML app requests, browser searches, payments, secrets, or private exposure.

## Quality Standard
Good Excel output has meaningful sheet names, useful headers, editable rows, sensible widths, frozen header/reference panes, formats where useful, formulas for totals when implied, and notes that help Zainal keep using the workbook.

## Safety
hard no: no private exposure, no secrets, no passwords, no OTPs, no bank or card data, no fake completion, no empty workbook, no generic one-row table pretending to be a useful spreadsheet.
Reject budget, cost, expense, tracker, or total-oriented workbooks that have no formulas.

## Local Validation
Open the workbook with `openpyxl`.
Check sheet count, populated cells, table-like rows, frozen panes, and formula cells when the topic implies calculations.

## Claude Review
Claude reviews an extracted workbook summary against this skill for usefulness, structure, missing columns, and whether the file is deliverable.

## Provider And Repair
Gemini drafts spreadsheet notes when model drafting is needed. Local libraries build the workbook. If QA rejects, repair once where available or deliver as a draft with issues.

## Delivery
iMac opens the workbook in Excel. Telegram attaches the workbook and keeps the path visible as text when useful.

## Activation Tests
happy path: user asks for a Tokyo travel budget tracker.
success: file opens, has useful categories, editable rows, formulas, and frozen panes.
failure path: workbook is empty or has no formulas for a budget/tracker request.
rollback: keep it as a draft and report QA issues instead of calling it final.
regression: asking what Excel is should not create a workbook.
expected: Maya creates files only for artifact requests.
