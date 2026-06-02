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

Visible slide text should be short, visual, and label-like. Explanatory sentences, caveats, and talk track details belong in speaker notes, not crowded slide bodies.

Internet-derived design baseline: one idea per slide, minimal visible text, strong visual hierarchy, large readable typography, useful whitespace, and visuals that explain the idea faster than text. Do not make slide bodies look like Word documents. Do not use generic text-card layouts as the default for travel, food, venue, product, pitch, tourism, or lifestyle topics.

When the topic benefits from visuals, good PowerPoint output should use generated or sourced visual assets instead of text-only slides. Generated images must support the slide message, not act as random decoration. Use Google/Gemini image generation by default for visual topics unless image generation is explicitly disabled or unavailable. Visual-topic decks should normally place at least one relevant image on every slide. The hard cap is `ceil(slide_count * 1.3)`, so a 10-slide deck may use at most 13 images.

Short prompts still need a real deck spine. Travel and food decks should include itinerary logic, food/place highlights, budget or logistics, and recommendations. Technical decks should include prerequisites, controlled setup/configuration, verification, and risk gates. Proposal decks should include the current gap, recommendation, implementation path, and decision risks.

Default image generation for PowerPoint is Nano Banana 2 / Gemini 3.1 Flash Image. Upgrade to Nano Banana Pro / Gemini 3 Pro Image for important final decks, professional pitch decks, complex image instructions, or high-fidelity visual assets. Do not use Grok for normal PowerPoint image generation because Grok is reserved for live voice, Pulse, current/news, and only explicit Grok requests.

Theme selection defaults to black/dark editorial for PowerPoint. Use pastel only when Zainal explicitly asks for pastel, light, bright, white, or says he does not want dark theme. Theme must still fit the visual asset: default dark decks need dark/editorial or high-contrast visuals, while explicit pastel decks need bright/high-key imagery.

## Safety
hard no: no private exposure, no secrets, no passwords, no OTPs, no bank or card data, no fake completion, no placeholder phrases, no unreadable slides, no broken render.
Reject decks that cannot open, cannot render, contain ellipsis overflow, have missing readable text, or contain generic placeholder labels such as `SLIDE FOCUS`.

## Local Validation
Open with `python-pptx`, render slide images, check render count, readable text, placeholder phrases, truncation, repeated/incomplete titles, sentence-heavy visible slides, and speaker-note presence for explanatory content.

## Claude Review
Claude reviews presentation structure, design quality, polish, and visual asset fit. `powerpoint_design_taste` is loaded as active taste context, and Design Engineering may be used as additional craft context.

## Provider And Repair
Gemini acts as the bounded content strategist and visual preflight agent: define the narrative spine, audience role, visual plan, and slide purpose before drafting. Gemini does not own final file quality by text alone. Local PowerPoint code creates the actual `.pptx`, local QA renders and checks it, Gemini image generation or safe sourcing adds visual assets when useful, and Claude reviews/polishes the result. One topic-safe repair/polish pass is allowed.

## Delivery
iMac opens the deck in PowerPoint. Telegram attaches only the final editable `.pptx` by default after QA passes and shows important file text separately from voice replies. Do not send rendered JPEG/contact-sheet previews in Telegram unless Zainal explicitly asks for a preview. If QA rejects the deck, do not attach the editable `.pptx` as a finished deliverable.

Store the PowerPoint QA/review result so `/review` can show the latest deck review status, reviewer model, and pass/fail reasoning.

Reference note: `maya_skills/research_notes/powerpoint_visual_design_internet.md`. Taste source adaptation: `maya_skills/active/powerpoint_design_taste.md`.

## Activation Tests
happy path: user asks for a Kampung AI Telegram features deck.
success: editable PPTX opens, renders, passes visual QA, and has a polish grade.
visual path: user asks for a pitch, product, travel, venue, or concept deck where images would improve comprehension.
success: deck includes relevant generated or sourced visuals that support slide meaning and still passes render QA.
failure path: render fails or slides contain placeholders.
rollback: call it a draft with known QA issues.
regression: discussion about a presentation without a creation request should not create a file.
expected: Maya preserves the existing high-quality iMac PPTX workflow.
