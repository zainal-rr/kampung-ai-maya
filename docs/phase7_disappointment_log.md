# Phase 7 Disappointment Log

Purpose: capture live-testing misses exactly when they happen. This file is the
roadmap source for the next build. Each entry should preserve what Zainal asked,
what Maya did, what should have happened, the current diagnosis, and status.

Tags:
`[ROUTE]` wrong lane/handler · `[SHALLOW]` thin answer · `[WRONG]` incorrect ·
`[FORMAT]` wrong shape · `[MEMORY]` recall/forget issue · `[SLOW]` too slow ·
`[SAFETY]` risky behavior · `[NOPACK]` missing domain pack · `[FOLLOWUP]` lost
thread · `[VOICE]` voice-specific.

## 2026-06-12

### D1 — Voice document handoff muted follow-up conversation

- **Tags:** `[VOICE]`, `[FOLLOWUP]`, `[FORMAT]`
- **Prompt / situation:** During iMac voice, Zainal discussed Cisco ISE and
  Meraki integration, then asked Maya to make a Word document.
- **What Maya did:** Maya acknowledged the document creation and the document
  work did run in the background. But while the background work was active,
  follow-up speech such as "it's for my ED" and "can you hear me, Maya?" was
  not answered. The live log showed repeated:
  `maya-hotkey-supervisor> cancelled pre-tool response`.
- **What Zainal expected:** Maya should hand the document work to the internal
  document path, keep the live xAI voice conversation open, and continue talking
  normally while the file is being created.
- **Evidence:** Voice session 24, exported at
  `/Users/zainalabidinjamal/Desktop/Maya/voice_sessions/voice-session-2026-06-12-07-13-2-v1.md`.
  The work record completed later and saved:
  `/Users/zainalabidinjamal/Desktop/Maya/documents/meraki-document-v1.docx`.
- **Diagnosis:** The supervisor used a broad "cancel pre-tool response" guard
  while background work was active. That protected against duplicate preambles,
  but it also cancelled normal follow-up replies.
- **Fix applied:** Narrowed the guard so it can cancel only one immediate
  duplicate preamble inside a short configurable window
  (`XAI_VOICE_SUPERVISOR_AUTO_CANCEL_SECONDS`, default 2 seconds). The live
  service was restarted through `Kampung AI.app`. Added active-artifact
  steering for Word, Excel, and PowerPoint: context before drafting starts is
  merged into the original request; context while drafting runs is captured as a
  revision and applied after the first artifact is created; later artifact edit
  phrases target the latest artifact session.
- **Verified:** `artifact_steering_smoke.py`,
  `xai_realtime_work_supervisor_smoke.py`,
  `xai_realtime_browser_supervisor_smoke.py`, `xai_realtime_stream_smoke.py`,
  and `py_compile` passed.
- **Steer safety:** Maya records the artifact fingerprint after creation/edit.
  If Zainal manually changes the file before a steer edit, Maya creates a new
  version instead of overwriting. PPTX steer changes create a new version by
  default because slide layout edits are higher risk.
- **Remaining follow-up:** Browser steering is implemented in the next slice:
  late browser updates are now re-routed through the browser skill as updates to
  the active page/task instead of being treated as unrelated literal searches.
  Agentic workflow steering remains a later slice because it needs stronger
  workflow-state and rollback semantics.
- **Live retest update 2026-06-16:** Word revision/continuity passed in live
  testing. Maya updated by creating a new/versioned document because QA did not
  pass the in-place path; Zainal accepted this behavior for now. Voice-facing
  file wording was also cleaned up: Maya should say the friendly file name in the
  Maya folder, not a slash path or `.docx` / `.xlsx` / `.pptx` extension, and
  should not offer to open a file that the tool already opened.
- **Follow-up fix 2026-06-16:** A live "what is the document name?" retest still
  exposed `.docx` because the earlier wording fix covered artifact tool results,
  but not `inspect_active_context` evidence. Active-context tool text now also
  sanitizes POSIX paths, macOS Word colon paths, and standalone Office filenames
  before xAI sees them. Regression coverage was added in `active_context_smoke.py`.
- **Second follow-up fix 2026-06-16:** The next live retest showed a different
  miss: Maya answered from the Word title (`Malaysia Document`) and then guessed
  `Malaysia Document.docx`, even though the real saved filename evidence was
  `add-document-v1`. Active-context evidence now exposes
  `active_file_display_name` separately from `active_title`, and the voice prompt
  says document-name / filename / saved-as questions should answer from
  `active_file_display_name`, not from the title. Regression coverage now checks
  both fields are present and that the filename field has no Office extension.
- **Final live retest update 2026-06-17:** Browser soak remained healthy after
  idle, Excel budget creation/status/name passed, and PowerPoint deck
  creation/status/name passed. Maya answered friendly file names such as
  `japan-budget-tracker-v1` and `tokyo-deck-v1` without saying `.xlsx` or
  `.pptx`.
- **Status:** Live-passed for Word, Excel, and PowerPoint artifact continuity
  at the Phase 7 bar. Keep future refinements as polish unless a new live miss
  appears.

### D1A — Active artifact steer command test item

- **Tags:** `[VOICE]`, `[FOLLOWUP]`, `[FORMAT]`
- **Test prompt:** "Make a Word doc about Meraki." Then, while Maya is working:
  "Actually, it's for my ED." Then manually edit the opened file and say: "Add a
  short executive summary."
- **Expected:** First steer is merged or applied to the active document task.
  After manual edit, Maya edits safely or creates a `v2` file instead of
  overwriting. Log the final file path, whether the action was merged, edited in
  place, or versioned, and whether the content actually reflects the steer.
- **Repeat:** One Excel steer and one PowerPoint steer. Excel may edit simple
  note/context changes in place if unchanged. PowerPoint should create a new
  version for steer changes.
- **Live retest update 2026-06-16:** Word version passed. A new/versioned Word
  document is acceptable when QA or overwrite safety makes in-place editing
  unsafe.
- **Final live retest update 2026-06-17:** Excel and PowerPoint artifact flows
  passed at the Phase 7 bar: created files were present in the Maya folders,
  status questions were answered from active work state, and file-name answers
  used friendly names without Office extensions.
- **Status:** Live-passed for Phase 7. Reopen only if a new wrong-target or
  wrong-file-name miss appears in field use.

### D2 — Browser follow-up committed too early and searched the wrong thing

- **Tags:** `[VOICE]`, `[FOLLOWUP]`, `[ROUTE]`
- **Prompt / situation:** During iMac voice, Zainal asked Maya to search for new
  games, then clarified "new game releases in 2026", then said "Maybe the
  Reddit one?" while looking at search results.
- **What Maya did:** Maya acted on the early partial request first, then treated
  "Maybe the Reddit one?" as a fresh Reddit search. Chrome ended up on
  `reddit.com/search/?q=Maybe+the+Reddit+one%3F` instead of opening the visible
  Reddit result from the Google results page. Maya also answered too quickly
  while Zainal was still stuttering/clarifying.
- **What Zainal expected:** Maya should wait slightly longer before committing
  the turn, treat "the Reddit one" as context for the existing Google result
  page, and open the visible Reddit result instead of searching Reddit for the
  literal sentence.
- **Evidence:** Voice session 25, exported at
  `/Users/zainalabidinjamal/Desktop/Maya/voice_sessions/voice-session-2026-06-12-07-38-3-v1.md`.
  Live Chrome was observed on the wrong Reddit search page during diagnosis;
  after cleanup Chrome is back to the Maya grouped `about:blank` tab.
- **Diagnosis:** The realtime turn detector was too eager
  (`XAI_VOICE_TURN_SILENCE_MS=1300`), and the browser router gave Reddit's
  site-specific search skill priority over a site-result follow-up. The result
  opener also trusted structured visible-result extraction too much; if that
  extractor missed the Reddit label while the page text contained it, Maya fell
  back to searching for `Reddit`.
- **Fix applied:** Raised the default live turn silence to 2200 ms, added
  start-window context capture for supervised voice work, routed site-result
  follow-ups such as "Maybe the Reddit one?" through Google Search result
  opening, cleaned punctuation from implicit result targets, and made the opener
  inspect page text before recovering with a new search. Follow-ups that arrive
  while a browser task is already running are now applied as a second safe
  browser-skill pass against the active task, so "the Reddit one" should open the
  visible Reddit result rather than searching Reddit for the literal sentence.
- **Verified:** `browser_capability_smoke.py`,
  `browser_site_skills_smoke.py`, `xai_realtime_work_supervisor_smoke.py`,
  `xai_realtime_browser_supervisor_smoke.py`, `xai_realtime_stream_smoke.py`,
  and `py_compile` passed.
- **Remaining follow-up:** Retest live with the same behavior: search for a
  topic, then say "the Reddit one" or "the YouTube one" while the result page is
  visible. Also watch Maya's wording around screen visibility; she should use
  active context directly when allowed instead of saying she cannot see.
- **Status:** Fixed in code; needs live confirmation during Phase 7.

### D3 — Reddit review follow-up opened a literal Reddit search

- **Tags:** `[VOICE]`, `[FOLLOWUP]`, `[ROUTE]`
- **Prompt / situation:** During iMac voice, Zainal asked to see a Witcher 3
  review, then asked Maya to open the Reddit review/result.
- **What Maya did:** Maya opened or left Chrome on a Reddit search page for the
  literal phrase `Can I, open the Reddit?` instead of opening the intended
  Witcher 3 Reddit review/thread. Maya then said Reddit was open, which was
  technically true but semantically wrong.
- **What Zainal expected:** Maya should use the active Google/results context,
  identify the visible Reddit result or relevant Reddit thread, open that page,
  and verify the title/URL before claiming it is open.
- **Evidence:** Voice session
  `/Users/zainalabidinjamal/Desktop/Maya/voice_sessions/voice-session-2026-06-12-12-41-0-v2.md`.
  Current Chrome state confirmed the selected Maya-group tab is
  `reddit.com/search/?q=Can+I%2C+open+the+Reddit%3F`, with the title
  `Can I, open the Reddit? - Reddit Search!`.
- **Diagnosis:** Browser follow-up steering now catches phrases like "the
  Reddit one", but this live case used a different shape: "Can I, can you open
  the Reddit?" after a review search. The browser skill treated that as a new
  Reddit search instead of a command to open the Reddit result related to the
  active review search. Verification was also too weak: Maya accepted "Reddit
  is open" without checking that the opened page matched the requested review.
- **Fix applied:** Added compact volatile browser-result context in the existing
  browser skill path. Search skills now store the latest provider, query, page
  title/URL, visible result metadata, and timestamp as `maya_browser_result_context`.
  Context-shaped follow-ups such as "open the Reddit", "open the Reddit review",
  and "can you open the Reddit" route through the Google result opener before
  the Reddit search skill. Plain "open Reddit" still opens Reddit normally.
- **Verification behavior:** Maya now verifies contextual opens before claiming
  success: the URL must match the requested site, literal search pages such as
  `reddit.com/search/?q=Can+I+open+the+Reddit` are rejected, and the opened page
  must mention the active topic when topic context is available.
- **Verified:** `browser_capability_smoke.py`,
  `browser_site_skills_smoke.py`, `xai_realtime_browser_supervisor_smoke.py`,
  `tests/smokes/browser_untrusted_action_guard_smoke.py`, `code_health.py`, and
  full `local_ci.py` passed (`61/61`, zero blocking failures).
- **Phase 7 live test:** Search for "The Witcher 3 review", then say "open the
  Reddit". Pass only if the actual Reddit review/thread opens in the Maya Chrome
  group and Maya names the verified page. Fail if she opens a Reddit search for
  the phrase or claims success without verification.
- **Live retest update 2026-06-15:** Part A browser testing improved but did not
  fully pass. Maya opened the Google search in the Maya Chrome group and captured
  the Reddit result URL, but `Open the Reddit thread at
  https://www.reddit.com/r/bali/comments/...` was blocked as if it were a
  posting/account action. Diagnosis: the read-only safety detector matched
  `comments` in the URL path as `comment`, even though opening a thread URL is a
  read action. This is a safety false-positive, not a Maya-group failure.
- **Follow-up fix:** Plain URL navigation is now treated as read-only browser
  navigation, not as a posting/commenting operation. The Reddit/account safety
  guard now blocks actual operation phrases such as writing/submitting a comment,
  posting, voting, subscribing, messaging, or uploading; it does not block a
  read-only Reddit thread URL because the path contains `/comments/`.
- **Sight activation note:** Screen sight is triggered by phrases like "look at
  my screen" / "what is on my screen". Cisco camera sight is triggered by
  phrases like "what can you see", "use your eyes", or "look around"; current
  config keeps `ENABLE_VISION_CAMERA=1` and `MAYA_DISABLE_IMAC_CAMERA=1`, so Maya
  should use the external/Cisco camera rather than the built-in iMac camera.
- **Status:** Fixed in code again after live retest; needs one more live Part A
  confirmation that Reddit thread URLs open in the Maya group.

### D4 — Browser conversation flow feels clunky

- **Tags:** `[VOICE]`, `[FOLLOWUP]`, `[ROUTE]`, `[SLOW]`
- **Prompt / situation:** During iMac voice, Zainal tried to search for a game
  review and steer Maya toward a Reddit result. The conversation included
  partial/stuttered phrases such as "Can you search the rejected review", "No,
  just search the rejected", "The Richard Free review?", then the correction
  "I mean the Witcher 3 game review", followed by "Can you find the Reddit
  one?", "Yes", and "Yes, please."
- **What Maya did:** Maya responded to partial speech too early, gave vague
  preambles like "Okay, I'm opening that now" and "I'm ready when you are",
  searched or answered before the topic was stable, opened/considered the IGN
  review first, then asked whether to open the Reddit discussion, then searched
  Reddit and asked whether to open the top post, and finally said she could not
  open that Reddit post directly.
- **What Zainal expected:** Maya should let the user finish the search phrase,
  keep one active browser task context, use the corrected topic
  (`The Witcher 3 game review`), and resolve "the Reddit one" / "yes please" as
  a direct continuation of that active result-opening task. The interaction
  should feel like one assistant carrying the thread, not a chain of separate
  searches and confirmations.
- **Evidence:** Voice session
  `/Users/zainalabidinjamal/Desktop/Maya/voice_sessions/voice-session-2026-06-12-14-08-3-v1.md`.
  Launchd stdout shows the sequence ending with: "I opened the Reddit search for
  The Witcher 3 Wild Hunt discussions... Would you like me to open that post?"
  followed by "Sorry, I can't open that Reddit post directly."
- **Diagnosis:** D3 fixes the specific literal "open the Reddit" route, but D4
  is broader: the voice/browser layer still lacks a smooth multi-turn browser
  action state. It treats "yes", "yes please", and corrected phrases as normal
  conversation unless they line up with existing result-open wording. The
  acknowledgement wording also fires before the browser action is actually
  grounded, making Maya sound like she has done something before verification.
- **Fix applied:** Added a lightweight pending browser action with a 10-minute
  TTL. Search skills now store the top openable result as metadata-only state
  (`provider`, `query`, `rank`, `title`) and clear it after a successful open.
  The voice supervisor now treats short confirmations such as "yes", "yes
  please", "open that", and "that one" as continuations of that pending browser
  action when one exists. The browser capability layer has the same fallback, so
  the fix is not voice-only.
- **Voice wording fix:** Removed the repeated "Okay"/"Got it" style from
  deterministic acknowledgements and tightened the realtime prompts: Maya should
  say only the short acknowledgement once, then report the final result directly
  without starting with "Got it", "Okay", or "Sure".
- **Live retest update 2026-06-15:** Browser group ownership passed for Google
  Search: the Seminyak search opened in the Maya tab group with verified group,
  tab, title, and URL facts. Tripadvisor eventually opened correctly in the Maya
  group, but the first tool call treated "Open the Tripadvisor page ... at
  https://..." as a Google search query instead of a direct URL open. This caused
  a clunky two-step flow before Maya called the cleaner `Open https://...`
  request and succeeded.
- **Follow-up fix:** URL-bearing open requests now route to direct read-only URL
  navigation before site/search routing, so "Open the Tripadvisor page at
  https://..." opens the URL instead of searching the whole sentence. The Chrome
  extension also tries to clear ordinary reading overlays after opening a page:
  Escape/scroll first, then close-style controls such as Close/No thanks/Accept
  cookies, and it stops if dismissal changes the page host. Login/payment/submit
  operations remain separate guarded actions.
- **Status:** Fixed in code again after live retest; needs one more live Part A
  confirmation that URL-bearing requests open directly and overlays no longer
  block reading.
- **Live retest update 2026-06-15, Redang/Tripadvisor:** The Redang Google
  search itself passed browser ownership: Chrome opened in the Maya group with
  verified `group_id`, `tab_id`, URL, and title. The TripAdvisor follow-up did
  not pass: Maya's tool call contained the correct TripAdvisor URL, but the
  browser capability router saw "beach resorts" and sent it to the Booking.com
  stay-search path, which asked for a location instead of opening the URL.
  Diagnosis: this was a child-skill routing miss, not a Chrome-click or Maya
  group failure.
- **Follow-up fix:** TripAdvisor is now included in the same active
  Google-result follow-up target set as Reddit/YouTube/etc. Natural phrases such
  as "open the Tripadvisor one" route through the Google visible-result opener,
  while URL-bearing TripAdvisor requests still bypass hotel/search routing and
  open as direct read-only navigation. The regression smoke also pins that
  `tripadvisor.com.my` pages verify as TripAdvisor results.
- **Live retest update 2026-06-15, games search:** Part A browser retest then
  passed the TripAdvisor and Reddit open flows, but exposed a separate routing
  bug. Maya/xAI asked for `Google search best video games 2026 so far`, yet the
  local browser capability router sent it to YouTube because it matched the word
  `video` inside `video games`. This is the same class of old substring bug:
  Python overrode an explicit Google-search tool request with a weaker generic
  video heuristic.
- **Follow-up fix:** Explicit Google-search requests now route to Google before
  generic YouTube/video routing. `search YouTube ...` still goes to YouTube, but
  `Google search best video games ...` stays on Google.

### D7 — Maya answers too fast during stutters and artifact work

- **Tags:** `[VOICE]`, `[FOLLOWUP]`
- **Prompt / situation:** During D1/D1A live testing, Zainal noticed Maya often
  answered as soon as he paused briefly or stuttered, which made the
  conversation feel rushed even when the content was good.
- **What Maya did:** The realtime session treated short pauses as end-of-turn
  signals and some deterministic acknowledgements/result prompts encouraged
  very compact replies. This made Maya start talking before Zainal had finished
  repairing the sentence.
- **What Zainal expected:** Maya should still feel responsive, but she should
  leave a little more room for stutters, repairs, and follow-up context such as
  "actually..." or "it's for my ED."
- **Diagnosis:** Two layers contributed: the default voice silence window was
  too short for natural live speech, and the voice prompts lacked an explicit
  pacing instruction at the realtime/result boundary.
- **Fix applied:** The default `XAI_VOICE_TURN_SILENCE_MS` is now 2200 ms.
  Maya's voice context now asks for clear sentence breaks and a small natural
  pause between sentences. Supervised voice results also explicitly avoid
  starting with repetitive "Got it", "Okay", or "Sure" phrasing.
- **Verified:** `xai_realtime_work_supervisor_smoke.py`,
  `xai_realtime_browser_supervisor_smoke.py`, and
  `xai_realtime_stream_smoke.py` passed. This still needs live confirmation
  because perceived pacing depends on the actual xAI voice model output.
- **Status:** Fixed in code; needs live Phase 7 confirmation.

### D5 — Browser open claimed success when Chrome was not actually opened

- **Tags:** `[VOICE]`, `[FOLLOWUP]`, `[ROUTE]`, `[WRONG]`
- **Prompt / situation:** During iMac voice, Zainal discussed PS5 open-world
  RPGs, asked for The Witcher 3 review, then said: "Can you, can you open it in
  my browser, please?"
- **What Maya did:** Maya called `run_browser_skill`, then said: "I have opened
  the Metacritic page for The Witcher 3 in your browser. You should see the
  review scores there now." Zainal replied that he could not see it in the
  browser. Maya then gave only a direct link instead of correcting the failed
  browser action.
- **What Zainal expected:** Maya should open or foreground the actual review
  page in the Maya Chrome group, verify the visible title/URL, and only then
  claim the page is open. If the browser cannot be controlled, Maya should say
  that directly.
- **Evidence:** Voice session
  `/Users/zainalabidinjamal/Desktop/Maya/voice_sessions/voice-session-2026-06-12-16-59-4-v1.md`.
  The tool transcript shows:
  `Result: I could not inspect Chrome yet: extension op 'page_text' failed: no Maya tab open yet`.
  `voice_work_requests` also recorded the related browser work as `completed`,
  even though the result text said Chrome was unavailable.
- **Diagnosis:** The browser tool returned an honest failure string, but
  `run_voice_browser_skill` marked every non-exception browser result as
  `completed`. The voice result prompt then let xAI summarize the failed tool
  output as if the browser action had succeeded. This is a false-success bug at
  the voice browser result boundary, separate from the D3/D4 follow-up routing
  fixes.
- **Fix applied:** Added browser-result failure classification in
  `xai_realtime_tools.py`. Results such as `I could not inspect Chrome yet`,
  `no Maya tab open yet`, extension-operation failures, unverified opens, and
  missing visible results now complete the voice work with `Status: failed`
  instead of `Status: completed`. The spoken-result prompt now explicitly says
  that failed work must be reported as failed and must not be described as an
  opened browser page. Also fixed the named-page open route: requests like
  "open the Metacritic page for The Witcher 3" now route to Google Search with
  the command wording stripped, instead of falling through to blank-page
  inspection.
- **Verified:** `xai_realtime_browser_supervisor_smoke.py`,
  `xai_realtime_work_supervisor_smoke.py`, `browser_site_skills_smoke.py`, and
  `browser_capability_smoke.py` passed. The new regression uses the exact live failure phrase
  `extension op 'page_text' failed: no Maya tab open yet` and asserts that the
  voice work status becomes `failed`. The browser capability regression asserts
  that Metacritic named-page opens use Google Search and create a cleaned search
  URL.
- **Phase 7 live test:** Ask Maya to open a visible review page in the browser.
  Pass only if Chrome visibly opens/foregrounds the page in the Maya group and
  Maya names the verified title/URL. If the extension/Maya tab is unavailable,
  Maya should say she could not open or verify it, not claim success.
- **Status:** Fixed in code; needs live Phase 7 confirmation after Maya restart.

### D6 — Incomplete Google Images request searched literal filler and recipe document name was generic

- **Tags:** `[VOICE]`, `[BROWSER]`, `[DOCUMENTS]`, `[NAMING]`, `[CHROME]`
- **Prompt / situation:** During iMac voice, Maya successfully kept talking while
  a recipe Word document was running in the background. Later Zainal started a
  browser request with a stuttered partial phrase: "Uh, no, I want to, I want
  you to Google search, uh, the", then clarified that he wanted a Google image
  search and finally said "Nasi lemak?"
- **What Maya did:** The document was created as
  `both-document-v1.docx`, which is too generic for a recipe file. Chrome also
  opened a literal Google Search for the partial filler phrase:
  `Uh, no, I want to, I want you to Google search, uh, the`. When Maya asked
  what image topic to search for, the short follow-up "Nasi lemak?" was not
  attached to the pending image-search clarification.
- **What Zainal expected:** The recipe document name should reflect the content,
  for example `shawarma-nasi-lemak-v1.docx` or at least `recipes-v1.docx`.
  A half-spoken Google/Search/Image command should ask for the missing topic
  without opening a literal filler query. The next short topic answer should
  complete the pending image search.
- **Evidence:** Voice session
  `/Users/zainalabidinjamal/Desktop/Maya/voice_sessions/voice-session-2026-06-13-06-25-2-v1.md`.
  Chrome evidence showed one tab at
  `https://www.google.com/search?q=Uh%2C+no%2C+I+want+to%2C+I+want+you+to+Google+search%2C+uh%2C+the`
  plus two `about:blank` tabs. One blank tab is the Maya extension anchor; the
  other was a stale non-Maya blank from earlier browser/open-tab attempts.
- **Diagnosis:** Two parser layers were too trusting. The Google Search child
  skill accepted filler-only speech as a valid topic, and the lower-level
  browser skill treated "search a Google image" as ordinary Google Search when
  no image topic followed the command. The browser layer also had no pending
  "image topic needed" state, so "Nasi lemak?" arrived as normal conversation
  instead of completing the image search. In the first live retest, xAI
  transcribed "Google search uh the" as "Can you Google say"; Maya then waited
  about 30 seconds on the strict Chrome-extension driver before even reaching
  the incomplete-query guard. For naming, the artifact slugger kept filler words
  like "both" and did not recognize recipe/dish subjects.
- **Fix applied:** Added a browser query guard for filler-only/incomplete
  queries. Both the Google Search skill and Google Images path now ask for a
  topic without opening Chrome when the query is only filler. Added pending
  browser clarification state so "search a Google image" followed by
  "Nasi lemak?" runs `google images Nasi lemak`. Improved recipe naming so dish
  names like shawarma and nasi lemak are preferred, and generic recipe requests
  become `recipes-v1.docx` rather than `both-document-v1.docx`. Browser
  controller startup is now lazy, so incomplete queries can be rejected or
  clarified without waiting for the Chrome extension bridge.
- **Semantic routing fix:** Added a conservative browser intent normalizer before
  the router. It repairs obvious ASR/voice slips such as `gind` -> `find` and
  `Google say` -> `Google search`, strips harmless stutter scaffolding before
  browser commands, then hands the cleaned request to the existing router and
  query guard. This is intentionally not a broad LLM guesser: risky actions and
  unclear topics still ask for clarification instead of executing.
- **Chrome blank-tab fix:** The Maya Chrome extension now reuses its
  `about:blank` anchor tab for the next real URL instead of leaving the anchor
  beside the content tab. The extension still may need one blank tab only when
  the Maya group is idle, because Chrome cannot keep an empty tab group alive.
- **Verified:** `artifact_naming_smoke.py`, `browser_skill_smoke.py`,
  `browser_capability_smoke.py`, `browser_site_skills_smoke.py`,
  `xai_realtime_browser_supervisor_smoke.py`, and `code_health.py` passed.
  `browser_capability_smoke.py` includes a regression where browser-controller
  construction is forced to fail; incomplete phrases still return a
  clarification immediately. The browser smokes also include misspelled/misheard
  voice phrases such as `Can you gind a Google image of nasi lemak` and
  `Can you Google say modern kampung house`.
- **Phase 7 live test:** Say "search a Google image" and pause; Maya should ask
  for the image topic without opening a literal search. Then say "Nasi lemak?"
  Pass only if Google Images opens for nasi lemak inside the Maya group and no
  filler-query tab appears. Create another recipe document and check the file
  name is content-specific rather than `both-document`.
- **Status:** Fixed in code; needs live Phase 7 confirmation after Maya restart.

### D8 — Status question became a Word edit and reopened the wrong document

- **Tags:** `[VOICE]`, `[DOCUMENTS]`, `[STEERING]`, `[STATUS]`, `[WRONG]`
- **Prompt / situation:** During the D1/D1A live rerun, Zainal asked Maya to
  make a Word document about Cisco. While the work was active, he asked a
  status-style question: "Um, what was the document that I told you to do just
  now?" He left the open Word windows as proof.
- **What Maya did:** Maya created `cisco-document-v1.docx`, but the follow-up
  status question was captured as a document-steering instruction. After the
  Cisco draft completed, Maya applied that question as a Word edit. Because the
  stale active artifact state still pointed at `google-document-v2.docx`, Word
  opened/updated the other document too.
- **What Zainal expected:** Maya should answer the status question from active
  work state, for example: "I'm making the Cisco Word document now." It should
  not edit any file, and it should not reopen a stale Word document.
- **Evidence:** Latest voice session
  `/Users/zainalabidinjamal/Desktop/Maya/voice_sessions/voice-session-2026-06-13-16-27-3-v1.md`.
  Word had both `google-document-v2.docx` and `cisco-document-v1.docx` open.
  `voice_work_requests` showed the Cisco document work completed, while
  `history` recorded the later edit as:
  `update that document to Um, what was the document that I told you to do just now?`
- **Diagnosis:** `looks_like_work_followup()` already knew many status phrases
  should not become steer commands, but it missed this natural wording:
  "what was the document..." The realtime supervisor then let the phrase enter
  the steering queue. The artifact resolver's newer explicit-first logic was
  correct, but because this was not a real steer, it still had a chance to fall
  through to stale active-document state.
- **Fix applied:** Expanded active-work status phrase detection and changed the
  realtime supervisor so status questions short-circuit into `voice_work_status`
  instead of normal follow-up capture. The status answer prompt now explicitly
  says: "Do not treat the question as an edit instruction." Status questions are
  logged as `supervised_voice_work.status_question`, not as artifact steer
  events.
- **Verified:** `xai_realtime_work_supervisor_smoke.py` now starts a Word task,
  asks the exact live-style question "what was the document that I told you to
  do just now?", and asserts that no new follow-up or steer event is created.
  `code_health.py` also passes with no new root files.
- **Phase 7 live test:** Start a Word document request, then ask "what was the
  document I asked you to make?" while it is still running. Pass only if Maya
  answers with the active document/work status and no extra Word document opens.
  Then say "Actually it's for my ED" and confirm that real steer text still
  updates the correct document.
- **Status:** Fixed in code; needs live Phase 7 confirmation after Maya restart.

### D9 — Partial speech started artifact work and made Maya disruptive

- **Tags:** `[VOICE]`, `[TURN_TAKING]`, `[DOCUMENTS]`, `[SUPERVISOR]`
- **Prompt / situation:** During live iMac voice, Zainal paused/stuttered while
  forming a document request: "Can you..." / "Can you make me a..." and later
  "No, I'm asking you to make me a Meraki." Maya spoke before the full request
  was clear.
- **What Maya did:** The local supervised-work classifier started artifact work
  from the incomplete phrase `Can you make me a`, said "I'm making that now,"
  then the tool result later asked what to make. When Zainal tried to correct
  the request, Maya again acknowledged work before knowing the artifact type,
  then asked whether it should be Word, Excel, or PowerPoint. This created a
  stack of short responses and made Maya feel like she was interrupting.
- **What Zainal expected:** Maya should behave like a natural realtime voice
  assistant: wait for a complete command, ask one clarification when the command
  is incomplete, and only acknowledge work after she has enough information to
  actually start it.
- **Evidence:** Voice session
  `/Users/zainalabidinjamal/Desktop/Maya/voice_sessions/voice-session-2026-06-13-18-04-1-v1.md`.
  The transcript includes:
  `Supervised voice work started from transcript: Can you make me a`, followed
  by Maya saying she was making it, then a tool result asking what to make.
- **Diagnosis:** The xAI realtime VAD/interruption path was not the root cause.
  Maya already uses xAI server-side turn detection with a longer silence window.
  The bug was our local classifier: the phrase `make me a` alone was enough to
  trigger supervised document work. That bypassed the realtime model's natural
  clarification behavior and caused deterministic acknowledgements to jump in
  too early.
- **Fix applied:** Superseded by D10's tool-seam refactor. Local Python no
  longer starts supervised work from any raw voice transcript, including
  complete-looking phrases. It only captures status and steering while a
  tool-started work item is already active. xAI owns whether the user has made
  a clear enough request and calls `start_maya_work` only then.
- **Verified:** `xai_realtime_work_supervisor_smoke.py` now pins that both
  `Can you make me a` and `I told you to make me a router config` create no
  work row and send no local acknowledgement from transcript text.
- **Phase 7 live test:** Say "Can you make me a" and pause. Pass only if Maya
  asks what you want her to make instead of saying she is already making it.
  Then say "make me a Word document about Meraki." Pass only if work starts
  normally after the complete request.
- **Status:** Fixed in code by D10; needs live Phase 7 confirmation after Maya
  restart.

### D10 — Local transcript rules were acting as Maya's brain

- **Tags:** `[VOICE]`, `[DOCUMENTS]`, `[SUPERVISOR]`, `[QA]`, `[ROUTE]`
- **Prompt / situation:** Follow-up discussion after D9 showed the stopgap was
  still architecturally wrong. Local code was trying to judge whether phrases
  like "router config", "Meraki", or "Word document about Meraki" were
  semantically complete. That made voice feel like a form, and it caused Maya
  to predict what Zainal meant.
- **What Maya did wrong:** Raw transcripts flowed into local readiness and
  domain-ish rules before xAI had finished understanding the turn. The local
  layer generated canned clarification wording and could start or reject work
  based on technical meaning.
- **What Zainal expects:** xAI/Maya owns meaning. If the request is unclear,
  Maya asks naturally or waits. If the request is clear, Maya calls a tool with
  the full intended request. Local Python only validates safety and mechanical
  executability.
- **Diagnosis:** The real seam is the xAI tool call. Any local code that reads
  raw transcript text and decides "this is ready technical work" becomes a
  second brain. That was the architecture failure.
- **Fix applied:** Removed local transcript-start behavior. `_maybe_start_supervised_voice_work`
  now only captures status/steering while a supervised tool-started item is
  already active. `start_maya_work` and `run_browser_skill` are the only iMac
  voice work-start seams. The remaining local argument guard is empty-only:
  local Python may reject a blank tool argument, but it must not decide whether
  a spoken request is semantically complete, too generic, or domain-valid. xAI
  receives `Status: needs_clarification` only for structural/safety reasons and
  phrases the user-facing question itself.
- **QA authority retained:** Soft-QA iMac edits still open as drafts for Word,
  Excel, and PowerPoint unless the issue is a hard block such as
  corrupt/unopenable file, unsafe overwrite, broken formulas, unsafe path, or
  sensitive/destructive external action.
- **Verified in code:** `xai_realtime_work_supervisor_smoke.py` covers no
  transcript auto-start, tool-call start for `make me a Meraki firewall config`,
  empty tool-argument rejection, pass-through of non-empty tool arguments
  without semantic readiness checks, artifact steering after tool-started work,
  and a regression that the local voice guard does not contain terms such as
  product/vendor/config-family words. `xai_realtime_browser_supervisor_smoke.py`
  covers the same no-transcript-start rule for browser work and confirms browser
  follow-ups still apply after a tool-started browser task.
- **Phase 7 live retest:** Say `Can you make me a` and pause. Pass only if no
  local work starts; Maya should either wait or ask naturally. Say
  `I told you to make me a router config... Meraki firewall config`. Pass only
  if Maya resolves the correction conversationally and calls `start_maya_work`
  once with the full intended request. Say `No wait, I mean...` and verify no
  premature local acknowledgement appears. During tool-started work, ask a
  status question; it should report status, not edit the document. If a soft QA
  warning happens, the draft should still open.
- **Status:** Fixed in code; live iMac voice proof still pending.

#### D10 Retest 1 — failed on stale/canned clarification behavior

- **Retest date:** 2026-06-14.
- **Observed:** Maya still asked, "Which platform and config goal? Cisco Catalyst
  VLAN, Meraki MX VPN, or Fortinet firewall policy?" and repeated the same
  clarification when Zainal tried to correct the request.
- **Diagnosis:** The live process was still showing the old rule-shaped voice
  behavior. The active source no longer contains that phrase, but Maya also
  needed a stricter spoken-behavior instruction so xAI does not recreate canned
  technical option lists on its own.
- **Follow-up fix:** Voice context now tells Maya to ask one open natural
  clarification question, not canned option lists or technical examples, unless
  Zainal explicitly asks for examples. It also tells Maya not to predict missing
  technical details from partial phrases, and to absorb corrections instead of
  repeating the previous clarification. `xai_realtime_stream.py` now logs a
  runtime marker on voice start:
  `voice_tool_seam=tool_call_only transcript_auto_start=disabled local_guard=empty_only_safety clarification_style=open_question_no_examples`.
- **Verification:** `xai_realtime_work_supervisor_smoke.py`,
  `xai_realtime_browser_supervisor_smoke.py`, `xai_realtime_stream_smoke.py`,
  `artifact_steering_smoke.py`, `browser_capability_smoke.py`, `code_health.py`,
  and full `local_ci.py` all pass after the follow-up fix. Kampung AI service was
  restarted after the fix.

#### D10 Retest 2 — Word clarification and three-day duration were lost

- **Retest date:** 2026-06-14.
- **Observed:** Zainal clearly answered "maybe a Word document", but Maya did
  not turn that clarification into a real document-generation call. Later, when
  the request explicitly said "three-day", the local artifact parameter checker
  still asked "How many days should the trip document cover?"
- **Diagnosis:** The voice tool seam still passed the work request as one raw
  string. Local document parsing returned a clarification question, but
  `start_maya_work` marked that result as `Status: completed`, so xAI treated it
  like finished work instead of a pending clarification. Separately,
  `explicit_day_count()` handled `3-day` and `three day`, but not `three-day`.
- **Follow-up fix:** `start_maya_work` now accepts structured xAI artifact
  meaning via optional `artifact_type` / `artifact_topic` arguments. If xAI knows
  the user means a Word document, local code receives a canonical Word-document
  request instead of guessing from the raw sentence. Local clarification replies
  now return `Status: needs_clarification`, with instructions for xAI to call the
  same tool again after Zainal answers. `explicit_day_count()` now recognizes
  word-number hyphen durations such as `three-day`. Voice artifact answers with
  filler, such as "Mean, maybe a Word document", now resolve to Word.
- **Tone fix:** Voice context now asks Maya to sound like a lively friend rather
  than a corporate support assistant, and bans generic service phrases like
  "I'm ready to assist" and "just let me know".
- **Reverted 2026-06-15:** Zainal asked to change Maya's personality/pacing
  prompt back to the earlier direct style. The semantic tool-seam and safety
  fixes remain; only the personality/pacing wording was reverted.
- **Verification:** `xai_realtime_work_supervisor_smoke.py` now pins both the
  clarification-status path and structured Word artifact path. Also passed:
  `artifact_clarification_continuity_smoke.py`,
  `document_natural_artifact_parser_smoke.py`, `xai_realtime_stream_smoke.py`,
  `xai_realtime_browser_supervisor_smoke.py`, `document_actions_smoke.py`,
  `code_health.py`, and full `local_ci.py`.

#### D10 Retest 3 — removed the last local semantic readiness checkpoint

- **Retest date:** 2026-06-15.
- **Observed:** The prior fix still left a Python regex gate that rejected
  non-empty tool calls when they looked like "unfinished action shells". That
  was still the wrong architecture: even if it had no Cisco/Meraki rules, local
  Python was still judging whether spoken language was complete.
- **Diagnosis:** The voice tool seam must be stricter. If xAI chooses to call
  `start_maya_work` or `run_browser_skill`, local Python may reject only blank,
  unsafe, or mechanically impossible actions. It must not reject a non-empty
  request because it thinks the wording is incomplete.
- **Follow-up fix:** Removed local semantic readiness from realtime tool
  execution. `xai_realtime_tools.py` and `xai_realtime_voice_work.py` now only
  reject empty tool arguments at this layer. `maya_voice/readiness.py` was
  deleted; there is no voice-readiness shim left for future code to reconnect.
- **Verification target:** Raw transcripts such as "Can you make me a" still
  cannot start work by themselves. But a non-empty xAI tool call now passes
  through to the work engine; if that tool call is semantically bad, the fix
  belongs in xAI instructions/tool calling, not in local transcript rules.

#### D10 Retest 4 — tool seam enforced with work state and controls

- **Retest date:** 2026-06-15.
- **Observed risk:** Even after deleting semantic readiness, Maya still needed
  a safe way to steer and cancel active work without reintroducing transcript
  interception. Cancellation also needed a concrete guarantee: cancelled work
  may finish an in-flight model/file call, but it must not open or deliver an
  artifact after Zainal says stop.
- **Follow-up fix:** Added phase state to `voice_work_requests`:
  `queued`, `drafting`, `building`, `qa`, `opening`, `done`, `failed`, and
  `cancelled`, plus `cancel_requested`, `cancel_reason`, `revision_count`, and
  `phase_detail`. Added xAI-callable `revise_maya_work` and `cancel_maya_work`
  tools. xAI decides whether an utterance is a steer or cancel; Python only
  resolves the work handle and applies mechanical state/file safety.
- **Revision guarantee:** If revision text arrives before/during drafting, it is
  folded into the request that the model receives, not merely recorded in an
  audit row. If the artifact already exists, Maya edits only when the file
  fingerprint still matches what Maya wrote; otherwise the existing steering
  path creates a safer versioned file. PowerPoint defaults to versioned copies.
- **Cancel guarantee:** Cancellation is cooperative, not instant. The safety
  property is that queued/drafting/building/QA work with `cancel_requested`
  cannot transition to `opening`; delivery code checks the current voice-work
  phase before opening Word, Excel, or PowerPoint.
- **Failure guarantee:** Tool execution failures now mark the work `failed`,
  store `phase_detail`, and return a structured function result to xAI so Maya
  narrates the failure instead of going silent.
- **Verification:** `xai_realtime_work_supervisor_smoke.py` now pins the
  behavioral seam invariant, no transcript auto-start, empty-only guard,
  work-phase transitions, ambiguous active-work resolution, revise-before-draft
  input folding, cancellation blocking `opening` from queued/drafting/building/
  QA, completed-work cancel behavior, and model-timeout failure reporting.
  `xai_realtime_browser_supervisor_smoke.py` passes with the same function-call
  machinery.
- **Live proof:** Pending. Run D1-D10 voice retests after the service restart;
  do not mark D10 live-closed until Maya behaves conversationally without
  canned readiness prompts.

#### D10 Retest 5 — manifest, evidence, confirmation, and strict-browser seam

- **Retest date:** 2026-06-15.
- **Observed risk:** The voice seam fix needed the return-direction half too.
  Maya must not only avoid local semantic readiness rules; she also must not
  claim that files opened, revisions persisted, browser pages opened in the Maya
  group, or confirmations were approved unless Python has fresh evidence.
- **Follow-up fix:** Added a voice artifact manifest at the `start_maya_work`
  boundary. Work now has a structured manifest before the document engine runs.
  Revisions patch that manifest with compare-and-swap; opaque prose revisions
  are forwarded without Python interpreting them. Word document titles can come
  from the manifest title field, with Python checking only mechanical title
  hygiene.
- **Render/evidence fix:** Word builds now emit render reports tied to the
  manifest version and artifact fingerprint. Count-bearing fields such as
  `duration_days` are mechanically checked against created Day sections. Active
  context now returns separated evidence blocks for selected text, live app
  text, saved-file parse, timestamps, provenance, and mechanical divergence
  such as `selection_absent_from_saved_parse`; it does not label semantic
  conflicts.
- **Trust fix:** Browser, OCR/screen, and user Office/PDF/file content are
  reference-only and `untrusted_for_commands` unless Maya created them in the
  current trusted flow. Missing Office/browser/screen permissions surface as
  `capability_unavailable` rather than silent emptiness.
- **Confirmation/browser fix:** Added structured confirmation storage with
  `action_id`, action fingerprint, expiry, and stale/version-conflict handling.
  Voice browser runs default to extension-strict mode; disconnected extension
  returns `browser_bridge_unavailable` instead of silently falling back to
  normal Chrome.
- **Browser availability hardening 2026-06-16:** Strict mode remains unchanged:
  Maya still cannot silently fall back to personal/normal Chrome. The bridge is
  now more self-healing when the Chrome extension service worker or socket goes
  stale: Python pings the extension before handing out a controller, drops a
  zombie client on timeout/send failure, gives the extension a clean reconnect
  window, and does not throttle strict-mode retries behind an old failed-start
  cache. The bridge implementation was moved into `maya_browser/` package
  helpers so the root file cap stays intact. Verified by
  `browser_extension_bridge_smoke.py`, `browser_driver_mode_smoke.py`,
  `browser_site_skills_smoke.py`, `browser_capability_smoke.py`,
  `xai_realtime_browser_supervisor_smoke.py`, and `code_health.py`.
- **Live retest update 2026-06-16:** Word passed and Browser Part A step 1
  passed: `Google search Langkawi travel guide` opened in the Maya Chrome group.
  Browser Part A step 2 failed: xAI correctly selected the second visible result
  URL, but Python treated the bare URL tool request as page inspection instead
  of direct navigation, so Chrome stayed on the Google results page. Follow-up
  fix: bare URL requests now route as read-only direct URL navigation, the same
  as `open https://...`. Regression coverage was added to
  `browser_capability_smoke.py` with the exact Wanderlust Chloe URL from the
  failed live test.
- **Reliability follow-up 2026-06-16:** A later voice session got stuck after
  `run_browser_skill` for `Google Sri Lanka visa`, leaving the session open until
  it was manually recovered. The browser voice tool now has a bounded timeout
  (`XAI_VOICE_BROWSER_TOOL_TIMEOUT_SECONDS`, default 45s) and returns
  `browser_tool_timeout` as a failed tool result instead of hanging the realtime
  session. Two starts in the same log also failed because the configured
  headphone microphone was temporarily unavailable; input resolution now retries
  after a PortAudio/CoreAudio refresh before failing.
- **Deeper runtime fix 2026-06-16:** The next live retest exposed that a timeout
  around the coroutine was not enough. Browser controller setup can block
  synchronously while waiting for Chrome/the extension, starving the realtime
  event loop that also watches `.maya_voice_stop`. The browser capability now
  runs in an isolated worker thread with its own event loop, so a blocked Chrome
  call cannot stop the voice loop from receiving stop triggers. The controller
  app was also rebuilt so quitting/restarting the hotkey controller no longer
  deletes the engine LaunchAgent by default; it requests a voice stop and leaves
  the engine service installed unless `KAMPUNG_AI_CONTROLLER_UNLOADS_SERVICE=1`
  is explicitly set. Session/work rows left open by the incident were marked
  recovered/failed, and a bounded live browser check opened `Google search
  Langkawi` in the Maya group with verified window/group/tab facts.
- **Verification:** New `tests/smokes/voice_semantic_seam_manifest_smoke.py`
  pins no transcript work-start, bool-only empty guard, manifest creation,
  manifest CAS, render-report mismatch detection, confirmation fingerprinting,
  and strict-browser fail-closed behavior. Full `local_ci.py` passed 63/63 with
  zero blockers.
- **Reviewer guardrail:** Two reviewer agents checked the code against the
  plan. The semantic-seam reviewer caught three blockers: raw browser follow-up
  transcripts were still being interpreted by Python, work kind/subtype was
  still derived from request text, and render-report mismatches were only
  recorded. The return-direction reviewer caught unverified browser-click
  wording, stale failure facts, stale manifest facts, missing-manifest revision
  success wording, and browser DOM no-data fallback. All were fixed before live
  retest.
- **Follow-up fixes from review:** Browser follow-ups now require a fresh xAI
  `run_browser_skill` tool call; Python no longer turns raw follow-up transcript
  into browser actions. Work kind comes from structured tool args, not request
  keywords. Count-bearing Word output is generated from manifest structure:
  if `duration_days=3`, the builder mechanically ensures Day 1 through Day 3
  sections exist before rendering, then records the render report. Unverified
  browser clicks now say they cannot confirm the result. Failed tool paths emit
  `work_active=false`. Final manifest facts are refreshed after revisions.
  Missing-manifest revisions fail. Browser DOM no-data returns
  `capability_unavailable` instead of screenshot fallback. iMac file delivery
  now says Maya asked the app to open the file unless the specific active file
  has been verified.
- **Final verification after reviewer fixes:** Focused voice/browser/document
  smokes passed, `code_health.py` passed, and full `local_ci.py` passed 63/63
  with zero blockers.
- **Live proof:** Pending. Restart Maya, then rerun D1-D10 voice tests before
  committing. Pay special attention to: no canned readiness options, correct
  document title, highlighted Word text evidence, no false “opened/working”
  narration, and all browser work staying inside the Maya Chrome group.

### D11 — Voice capability contradiction and name-heavy tone

- **Tags:** `[VOICE]`, `[FOLLOWUP]`, `[WRONG]`
- **Prompt / situation:** During live iMac voice testing, Zainal highlighted text
  in Chrome on the Cisco Meraki MX Family Datasheet and asked Maya to explain the
  highlighted part. The same session also felt generic because Maya repeatedly
  said "Zainal" in short action-result replies.
- **What Maya did:** Maya spoke with a generic bridge and then used
  `inspect_active_context`. The tool successfully returned active browser
  selection evidence: `quality of experience (QoE)`. Maya then answered the
  concept correctly, but still hedged that the exact highlighted text did not
  come through clearly. She also used Zainal's name repeatedly in short turns
  such as browser/document confirmations.
- **What Zainal expected:** If Maya has an active-context tool result with
  selected/highlighted text, she should say she can read it and explain it
  directly. If a capability is unavailable, she should say that specific
  capability is unavailable. Maya should avoid sounding generic or repeating the
  user's name after every action.
- **Diagnosis:** The capability itself worked. The contradiction came from the
  return-direction prompt/evidence boundary: active context exposed the selected
  text as `anchor`, not as a clear `selected_text` block, and the voice prompt did
  not positively tell Maya to narrate from selected text first when selection
  evidence exists. The tone issue came from prompt examples and result narration
  allowing frequent name use.
- **Fix applied:** `voice_context.py` now tells Maya to use Zainal's name
  sparingly, add more relaxed vocal color, and narrate from selected/highlighted
  text first when `inspect_active_context` returns selected text, selected-text
  chars, or an anchor block. `active_context_models.py` now emits
  `selected_text_present: true` and a `selected_text:` block before the legacy
  `anchor:` field, so the evidence is unambiguous for the voice model.
- **Verified:** `active_context_smoke.py`,
  `tests/smokes/voice_semantic_seam_manifest_smoke.py`,
  `xai_realtime_stream_smoke.py`, `code_health.py`, and full `local_ci.py` passed
  63/63 with zero blockers after the fix.
- **Live retest sample:** On 2026-06-15, the latest voice session
  `voice-session-2026-06-15-09-04-5-v1.md` showed 21 Maya replies with zero
  spoken `Zainal` name mentions in Maya's replies. The selected-text evidence
  path worked for both browser and Word: Maya received
  `selected_text_present: true`, then correctly said she could see the
  highlighted browser text and the highlighted Word paragraph. Zainal also
  reported that Maya's voice felt better.
- **Remaining observation:** The same log also showed a browser-result follow-up
  rough edge: Google searches still failed browser-group verification when the
  Maya Chrome extension/group was not available, but Maya reported the failure
  honestly instead of claiming Chrome opened. Keep this under D10/D2 browser
  ownership rather than D11 tone/capability-honesty.
- **Tracking note:** The action-contract/revision/browser work remains tracked
  under D10 Retest 5. D11 is only the capability-honesty and name-heavy-tone
  issue from the highlighted-text live test.
- **Status:** Live sampled pass for D11 tone and selected-text capability
  honesty. Keep sampling during Phase 7 because tone is eval-style behavior, not
  a one-run deterministic guarantee.
- **Prompt status 2026-06-15:** Personality/pacing wording was later reverted to
  the earlier direct prompt at Zainal's request. The selected-text evidence fix
  remains active.

### D12 — Voice answers overexplain simple browser/travel prompts

- **Tags:** `[VOICE]`, `[SHALLOW]`, `[FORMAT]`
- **Prompt / situation:** During Part A browser retesting, Zainal asked about
  Bali/Seminyak beaches and expected a short conversational answer.
- **What Maya did:** Maya listed five beaches with long descriptions, then added
  extra travel-planning questions. The answer was useful, but it sounded like a
  mini travel article rather than how someone would normally talk in voice.
- **What Zainal expected:** For voice, Maya should keep the earlier direct style:
  brief simple answers, with enough detail for active-context answers when
  useful.
- **Evidence:** Voice session
  `/Users/zainalabidinjamal/Desktop/Maya/voice_sessions/voice-session-2026-06-15-13-11-5-v1.md`.
  The 13:13 reply gave five beaches with full descriptions after a casual
  recommendation request.
- **Diagnosis:** This is not a tool failure. It is a voice-answer shape issue:
  Maya should not turn casual voice questions into mini articles.
- **Status:** Live pass by owner acceptance on 2026-06-16. The temporary
  three-to-five-sentence personality/pacing rewrite was reverted on 2026-06-15
  at Zainal's request, and Zainal confirmed he will raise a new complaint if
  Maya's tone or explanation length feels wrong again.

### D13 — Recommendation questions over-route into browser/YouTube work

- **Tags:** `[VOICE]`, `[BROWSER]`, `[TOOL-CHOICE]`
- **Prompt / situation:** During Part A browser retesting, Zainal asked:
  "Can you tell me the best game in 2026?" and then clarified that he wanted a
  recommendation, not a browser search.
- **What Maya did:** Maya treated the conversational recommendation question as
  browser work, called `run_browser_skill` with `Google search best video games
  2026 so far`, and local routing then opened YouTube because the query contained
  the phrase `video games`.
- **What Zainal expected:** Maya should understand semantically whether the next
  move is a normal voice answer or actual browser operation. If Zainal wants a
  site such as YouTube, he will say so naturally; Maya should not turn ordinary
  conversation into background browsing just because the web might add detail.
- **Diagnosis:** This had two layers. The root issue was xAI tool choice: Maya
  reached for `run_browser_skill` for a normal recommendation question. The
  secondary issue was local routing precedence: after the tool call, Python saw
  `video` inside `video games` and sent an explicit Google request to YouTube.
- **Fix applied:** `voice_context.py` and the `run_browser_skill` tool
  description now frame browsing as a semantic tool choice: use the browser when
  the intended next action is browser operation, not as background research by
  habit. Explicit Google-search tool requests now route to Google before generic
  YouTube/video routing.
- **Architecture note:** The explicit Google-vs-YouTube precedence is a stopgap,
  not the root fix. The durable follow-up is a structured browser target such as
  `target="google" | "youtube"`, emitted by Maya/xAI, so Python does not infer
  the destination from query text.
- **Verification:** Static contract smokes pin the voice prompt and tool
  description. Deterministic routing smokes pin that `Google search best video
  games ...` stays on Google while `search YouTube ...` still uses YouTube.
- **Live proof:** Passed on
  `/Users/zainalabidinjamal/Desktop/Maya/voice_sessions/voice-session-2026-06-15-17-55-1-v1.md`.
  Maya answered the PS5 action/open-world RPG request conversationally, used
  YouTube only after Zainal asked for a YouTube video, clicked the first YouTube
  result with verified Maya-group facts, opened Reddit when asked for Reddit
  reviews, and read the highlighted OpenCritic text from the active page. A
  2026/current-gameplay request may reasonably choose browser lookup because the
  model may not know current 2026 releases yet; that is not a D13 failure when
  Maya is choosing lookup for freshness rather than browsing by habit.
- **Follow-up fixed from the same live run:** "click the first post" was
  overblocked because the browser safety gate treated the noun `post` as a write
  action. The fix is route-based, not phrase-based: visible result/link opening
  is read-only navigation, while explicit write/account operations such as
  create/submit post/comment, vote, subscribe, upload, or send message remain
  blocked.

### D14 — Browser bridge readiness can fail during live voice

- **Tags:** `[VOICE]`, `[BROWSER]`, `[RELIABILITY]`, `[NO-QUICK-FIX]`
- **Prompt / situation:** Zainal restarted the browser test and said:
  "Google search Langkawi." The expectation was that Maya should either open the
  search inside the Maya Chrome group or fail honestly without freezing; the stop
  hotkey must keep working.
- **What Maya did:** The voice session stayed alive and eventually closed with
  `manual_stop`, so the earlier full event-loop freeze did not reproduce.
  However the browser work still failed after a long wait. The work row
  `vw_4307fcfe1a70` ended as `failed` with `browser_tool_timeout` and verified
  facts showed `browser_bridge_connected=false` and
  `opened_in_maya_group=false`.
- **Evidence:** The live engine LaunchAgent remained loaded and running. The
  engine owned the local bridge ports `8975` and `8976`, and `/health` returned
  `maya-extension-bridge-ok`, proving the bridge server was listening. Chrome
  had the unpacked Maya extension installed at
  `chrome_extension/maya`, and the extension's stored token matched
  `logs/extension/maya_extension_token.txt`. Later inspection showed an
  established websocket between Chrome and the engine, meaning the extension can
  reconnect after the failed command. The problem is therefore intermittent
  live bridge readiness, not a missing token or absent LaunchAgent.
- **Diagnosis:** The current health check proves only "server is listening";
  it does not prove "Chrome extension client is connected and ready for a
  command." The previous bounded Codex runtime check proved that a temporary
  Python process could control Chrome, but that is not equivalent to proving the
  live Maya engine owns a connected extension bridge. Browser proof must be
  against the live engine bridge, not a throwaway bridge process.
- **Fix implemented:** Browser readiness now separates server health from live
  extension ownership. `/health` still means server-listening only, while
  `/status` is query-only and reports owner kind, server PID, client connection,
  ping freshness, and reason code. The Maya engine starts an engine-owned
  warmup monitor, browser voice work enters a `preflight` phase before Chrome
  execution, and strict mode fails quickly with `browser_bridge_unavailable`
  when the engine-owned extension client is not connected/pingable. Unknown
  bridge port owners return `bridge_port_contended` and require manual cleanup;
  Maya does not kill unknown processes blindly.
- **Follow-up after first live retest:** The first D14 implementation made the
  failure honest but not available. The live status flipped from connected to
  unavailable because the warm monitor used a 1s active ping and closed the
  Chrome socket on any ping timeout. That was too aggressive for an MV3 service
  worker. Readiness pings are now non-destructive, timeout defaults are less
  brittle, and only truly stale clients are closed. After restart, `/status`
  stayed `owner_kind=engine`, `client_connected=true`, and `reason_code=connected`
  past the previous failure window.
- **Lifecycle fix:** The remaining failure was not "Chrome connectivity" in
  general. Chrome could work normally while the Maya extension service worker
  was detached from the engine bridge. The extension now declares Chrome 116+
  and runs a 20s in-worker heartbeat over the WebSocket so the service worker
  stays active while connected. Voice browser preflight now defaults to a 12s
  reconnect ceiling, returning immediately when the bridge is warm.
- **Operating rule from Zainal:** For live Maya failures, analyze the whole
  chain first: DB work row, voice transcript, LaunchAgent, controller hotkey
  path, browser bridge server, Chrome extension client, and user-visible app
  state. Do not make quick code fixes until the failure class is understood.
- **Live proof 2026-06-17:** Passed. The live engine-owned bridge stayed
  connected after idle (`owner_kind=engine`, `client_connected=true`,
  `reason_code=connected`). Maya searched Langkawi in the Maya Chrome group and
  opened the third visible result (`naturallylangkawi.my`) with verified
  group/window/tab facts. Zainal accepted this as the browser bridge pass.
- **Residual note:** `voice_action_promise_without_tool` remains an observability
  audit, not full prevention. Some bridge/tool-first phrasing may still be
  logged, but Phase 7 live behavior is accepted unless a new user-visible miss
  appears.
- **Status:** Live-passed for Phase 7.
