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

Good Word output is measured by more than file existence. The document must pass all of these checks:
1) scenario fit: headings and content match the requested document type.
2) section depth: each required section has useful topic-specific content, not a one-line label.
3) actionability: the reader can use the file without asking Maya to add basic missing parts.
4) specificity: travel documents name real route/food/budget/transit details, technical guides name concrete configuration and verification steps, and proposals name real scope, deliverables, risks, and next actions.
5) repair readiness: if local QA or Claude rejects the file, Maya must attempt one repair pass before delivery.

## Scenario Structures
Maya should choose the document structure from the user's real scenario instead of reusing one generic outline.

travel itinerary: Trip Overview, day-level plans, place or food highlights, budget notes, booking/transit notes, and recommendations.
If the user asks for a short city food trip document without a duration, default to a compact 2-day plan and state that assumption. Do not create a sprawling 5-day plan from a short voice/text request.
technical guide: Purpose, Prerequisites, Configuration Steps, Verification, Troubleshooting, Safety Notes, and Next Steps.
Router/WiFi technical guides must include admin interface login, changing the default admin password, WAN/internet setup, SSID/WiFi name, WiFi password, WPA2/WPA3 security, firmware update, and final connectivity verification.
proposal: Executive Summary, Objective, Scope, Recommended Approach, Deliverables, Timeline, Risks, and Next Steps.
Proposal sections must not contain empty labels such as Out of Scope without content. If a framework is named as two-step, three-tier, or similar, every promised step or tier must be present.
research brief: Research Question, Scope, Key Findings, Evidence, Risks Or Unknowns, Sources, and Next Steps.
checklist: Checklist Overview, Must Do, Should Do, Optional, Risks Or Watchouts, and Done Criteria.
meeting notes: Meeting Summary, Decisions, Action Items, Open Questions, and Follow Up.
letter: Recipient, Subject, Opening, Request, Supporting Details, Requested Resolution, and Closing.
report: Executive Summary, Findings, Evidence, Impact, Recommendations, and Next Steps.
plan: Goal, Context, Workstreams, Timeline, Risks, and Next Steps.
explainer: Plain-English Summary, Core Concept, Why It Matters, Examples, Common Confusions, and Next Steps.

Generic boilerplate headings such as Role And Assumptions, Working Context, Key Decisions, Review Checklist, Needs Verification, and Confidence should not appear in normal Word documents unless Zainal explicitly asks for an audit-style structure.

## Safety
hard no: no private exposure, no secrets, no passwords, no OTPs, no bank or card data, no fake completion, no malformed markdown, no placeholder sections unless the user asked for a template.
Reject files with lorem ipsum, TODO-only content, raw code fences, `###` markdown artifacts, empty headings, or very thin text.

## Local Validation
Open the `.docx` with `python-docx`.
Check heading presence, paragraph density, placeholder text, malformed markdown remnants, and openability.
Check that the headings fit the detected scenario and that scenario-specific required sections are present.
Check that required sections are not thin or meta-commentary such as "this section should include..." or "model generated content."
Run local Word visual QA before calling a document polished: first visible paragraph should be title/heading styled, headings should be readable and not repeated, margins should be sane, and body paragraphs should not be visually dense walls of text. Optional macOS `textutil` preview may be used as extra proof, but structural layout heuristics still run without it.

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
