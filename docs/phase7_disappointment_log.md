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
- **Remaining follow-up:** Browser and agentic workflow steering are not part of
  this slice. Live testing should still confirm whether Word/Excel/PPTX steering
  feels natural enough.
- **Status:** Fixed in code; needs live confirmation with Word, Excel, and PPTX
  steering prompts.

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
- **Status:** Added for Phase 7 live testing.

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
- **Fix applied:** Raised the default live turn silence to 1800 ms, added
  start-window context capture for supervised voice work, routed site-result
  follow-ups such as "Maybe the Reddit one?" through Google Search result
  opening, cleaned punctuation from implicit result targets, and made the opener
  inspect page text before recovering with a new search.
- **Verified:** `browser_capability_smoke.py`,
  `browser_site_skills_smoke.py`, `xai_realtime_work_supervisor_smoke.py`,
  `xai_realtime_browser_supervisor_smoke.py`, `xai_realtime_stream_smoke.py`,
  and `py_compile` passed.
- **Remaining follow-up:** Retest live with the same behavior: search for a
  topic, then say "the Reddit one" or "the YouTube one" while the result page is
  visible. Also watch Maya's wording around screen visibility; she should use
  active context directly when allowed instead of saying she cannot see.
- **Status:** Fixed in code; needs live confirmation during Phase 7.
