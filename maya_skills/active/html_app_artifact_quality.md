# HTML App Artifact Quality

## Maya Activation Wrapper
Active artifact quality skill. Progress is tracked only in `KAMPUNG_AI_CHECKLIST.md`.

## Purpose
Make Maya send real `.html` app files instead of pasting broken code into Telegram.

## Trigger Phrases
trigger: create, make, draft, build, review, repair, or save an HTML file, single-file app, web app, mini app, dashboard, planner, tracker, or tool.
non-trigger: normal chat, Word-only requests, Excel-only requests, PowerPoint-only requests, payments, secrets, private exposure, or general web browsing.

## Quality Standard
Good HTML output is a complete saved file with doctype, html/head/body, inline CSS, inline JavaScript, real controls, mobile responsiveness, and usable app behavior. It should open directly in a browser.

## Safety
hard no: no private exposure, no secrets, no passwords, no OTPs, no bank or card data, no fake completion, no pasted source in Telegram, no malformed tags, no broken CSS property names, no code fences, no specification wrapper.
Reject `<.DOCTYPE html>`, `UTF 8`, `width=device width`, `initial scale`, CSS properties with spaces, missing script, or no interactive controls.

## Local Validation
Check single-file structure, app markers, interactive controls, common malformed syntax, and code-fence leakage. Browser smoke/render should be used when available.

## Claude Review
Claude reviews the generated file after Kimi or Gemini produces it. Claude may repair HTML but must return only the complete file.

## Provider And Repair
Kimi K2.6 is primary coder. Gemini Flash is fallback only after Kimi fails or times out. Claude reviews the file. Local validation decides whether Maya may call it final.

## Delivery
iMac opens or saves the HTML under Desktop Maya artifacts. Telegram attaches the `.html` file and does not paste code unless Zainal explicitly asks for code.

## Activation Tests
happy path: user asks for a travel planner app.
success: file exists, opens as an app, has form/control behavior, and no malformed CSS/HTML.
failure path: Kimi times out or produces broken source.
rollback: Gemini fallback runs; if QA still fails, deliver as a draft with issues.
regression: typo such as `ake me a html file` is still recognized as an HTML file request.
expected: Maya sends the file, not a long code block.
