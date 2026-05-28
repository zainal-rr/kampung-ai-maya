# PowerPoint Artifact Quality

## Maya Activation Wrapper
Active artifact quality skill. Progress is tracked only in `KAMPUNG_AI_CHECKLIST.md`.

## Purpose
Preserve the stronger iMac-style PowerPoint workflow as the standard for every channel.

## Trigger Phrases
trigger: create, make, draft, review, polish, or repair a PowerPoint, PPTX, slide deck, presentation, or slides.
non-trigger: normal chat, Word-only requests, Excel-only requests, HTML app requests, payments, secrets, or private exposure.

## Quality Standard
Good PowerPoint output is editable, visually readable, has strong slide titles, short supporting copy, no placeholder language, no repeated weak slide titles, and no overflow/truncation.

## Safety
hard no: no private exposure, no secrets, no passwords, no OTPs, no bank or card data, no fake completion, no placeholder phrases, no unreadable slides, no broken render.
Reject decks that cannot open, cannot render, contain ellipsis overflow, or have missing readable text.

## Local Validation
Open with `python-pptx`, render slide images, check render count, readable text, placeholder phrases, truncation, and repeated/incomplete titles.

## Claude Review
Claude reviews presentation structure, design quality, and polish. Design Engineering skill may be used as design taste context.

## Provider And Repair
Gemini creates role-based slide content. Claude reviews. Local PowerPoint builder creates the file. Local QA renders and checks slides. One topic-safe repair/polish pass is allowed.

## Delivery
iMac opens the deck in PowerPoint. Telegram attaches the deck and shows important file text separately from voice replies.

## Activation Tests
happy path: user asks for a Kampung AI Telegram features deck.
success: editable PPTX opens, renders, passes visual QA, and has a polish grade.
failure path: render fails or slides contain placeholders.
rollback: call it a draft with known QA issues.
regression: discussion about a presentation without a creation request should not create a file.
expected: Maya preserves the existing high-quality iMac PPTX workflow.
