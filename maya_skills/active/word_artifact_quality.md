# Word Artifact Quality

## Maya Activation Wrapper
Active artifact quality skill. Progress is tracked only in `KAMPUNG_AI_CHECKLIST.md`.

## Purpose
Keep Maya-created `.docx` files useful enough to deliver from either iMac or Telegram.

## Trigger Phrases
trigger: create, write, draft, make, review, or repair a Word document, `.docx`, report, itinerary, checklist, proposal, note, plan, or letter.
non-trigger: normal chat, spreadsheet-only requests, PowerPoint-only requests, HTML app requests, browser searches, payments, secrets, or private exposure.

## Quality Standard
Good Word output has a clear title, useful headings, real owner-focused content, practical assumptions, concrete steps or decisions, and no generic filler.
It adapts structure to the artifact: itinerary, report, proposal, notes, plan, letter, or checklist.
It includes a short artifact summary for latest-document recall.

## Safety
hard no: no private exposure, no secrets, no passwords, no OTPs, no bank or card data, no fake completion, no malformed markdown, no placeholder sections unless the user asked for a template.
Reject files with lorem ipsum, TODO-only content, raw code fences, `###` markdown artifacts, empty headings, or very thin text.

## Local Validation
Open the `.docx` with `python-docx`.
Check heading presence, paragraph density, placeholder text, malformed markdown remnants, and openability.

## Claude Review
Claude reviews extracted document text against this skill for clarity, usefulness, completeness, and whether Maya can honestly call it final.

## Provider And Repair
Gemini drafts role-based content. Local libraries build the `.docx`. If local or Claude QA rejects, run one repair pass when available; otherwise deliver as a draft with issues.

## Delivery
iMac opens the document in Word. Telegram attaches the document and keeps filename/path visible as text when useful.

## Activation Tests
happy path: user asks for a two-day Kyoto Word itinerary.
success: file opens, has title/headings, concrete itinerary content, and no placeholders.
failure path: generated document has only placeholder text or malformed markdown.
rollback: keep it as a draft and report QA issues instead of calling it final.
regression: normal conversation about Word does not create a file.
expected: Maya only creates files when the request is an artifact request.
