# Kampung AI: The "Friendship" Implementation Checklist

This document tracks the technical and operational roadmap for building the standalone, headless Kampung AI.

## 🛠️ Phase 1: Foundation (The Body & Ears)
*Goal: Get the Python engine running and connected to Zainal via Telegram.*

- [x] **1.1. Environment Setup**
    - [x] Install Python 3.12 (iMac is on 3.14).
    - [x] Create project directory: `~/projects/kampung-ai`.
    - [x] Initialize Virtual Env.
- [x] **1.2. API Provisioning (Live provider smoke passed May 2026)**
    - [x] **Telegram:** Token secured in .env.
    - [x] **OpenAI:** Maya strategic lane (GPT-5.5).
    - [x] **Anthropic:** The Steward review lane (Claude Opus 4.8).
    - [x] **Google:** The Sight default and premium lanes (Gemini 3.1 Flash and Gemini 3.5 Flash).
    - [x] **Codex:** Codex CLI is installed for The Artisan coding lane; service-auth/live smoke remains tracked in 2.5.
    - [x] **xAI:** The Pulse (Grok 3).
    - [x] **xAI:** Ara voice notes, STT, and pulse/news lane.
    - [x] **xAI:** Live iMac Grok Voice Agent websocket path tested before May 25, 2026; iMac voice could continue conversation and trigger Word, Excel, and PowerPoint creation.
    - [x] Move the remaining live-key day to May 20, 2026.
- [x] **1.3. Conductor Setup (`main.py`)**
    - [x] Write the asynchronous entry point.
    - [x] Initialize SQLite database.
    - [x] Implement the **"Friendship Guard" (Output Masking)**.
- [x] **1.4. Channel Model Lock**
    - [x] Define the iMac as the **primary** interaction channel.
    - [x] Keep Telegram as a **secondary remote** channel.
    - [x] Avoid building a visible iMac UI unless needed for maintenance/debugging.
    - [x] Use Terminal as the short-term development host only.
    - [x] Plan a dedicated Kampung AI app/service identity for the long term.
    - [x] Add a `launchd` background-service path for the spare iMac.
    - [x] Lock the calm default posture: routines on, Omi adapter off until hardware day, and Mudra Link used only as external hotkey pass-through when configured.
    - [x] Keep the iMac voice loop off during pre-key testing so Telegram is the main live quality surface.
    - [x] Add activation rules for Telegram work-location commands, external camera only, and deliberate hotkey voice. Mudra Link may trigger voice only by emitting the same hotkey.
    - [x] Add a travel testing plan where Telegram is the main away surface and Splashtop is remote maintenance only.

## 🧠 Phase 2: The Shared Brain
*Goal: Wire the model lanes so every provider does its own job correctly.*

- [x] **2.1. The Primary Voice Presence (Grok Voice Agent + Ara)**
    - [x] Make Grok the default live iMac conversation model.
    - [x] Make Ara the default Maya voice identity on the iMac.
    - [x] Keep the iMac path optimized for fluid spoken interaction.
    - [x] Lock the voice agent budget rule: manual trigger starts it, 5 seconds of silence closes it, and it is never open all day.
    - [x] Remove live voice wake activation from the roadmap. `Option + Space` is the current deliberate iMac voice trigger; Mudra Link Mouse Mode can press that same hotkey externally.
    - [x] Add a bounded Grok Voice Agent session manager with stub transport for pre-key testing.
    - [x] Track Grok Voice Agent route and active seconds for `/route` and `/cost`.
    - [x] Prepare the real xAI websocket adapter behind disabled `real` mode.
    - [x] Keep `grok-voice-latest` as the xAI-recommended realtime voice model alias, with Ara as Maya's voice.
    - [x] Add speech audio input for the real Grok Voice Agent path after manual trigger.
    - [x] Replace diagnostic file-capture voice with realtime microphone streaming for the hotkey path.
    - [x] Stream audio chunks to Grok Voice Agent instead of recording a local PCM file first.
    - [x] Use server-side turn detection for live Grok voice conversation.
    - [x] Stream Ara audio back as it arrives instead of waiting for full WAV playback.
    - [x] Treat the current `ffmpeg` capture path as diagnostic only, not the natural iMac voice path.
    - [x] Prevent the real iMac voice-agent path from falling back to separate TTS after wake.
    - [x] Add iMac voice policy so short Malay/Manglish can stay on Grok while longer or style-sensitive Malay/Manglish routes to Gemini plus Ara.
    - [x] Add natural Ara thinking fillers for slower Malay/Manglish quality turns.
    - [x] Record the in-session work rule: longer voice requests start Maya's local work while the realtime voice session remains available.
    - [x] Add `run_browser_skill` and `start_maya_work` as the clean realtime voice facade tools for local browser and work execution.
    - [x] Add voice work state so Maya can report queued, running, completed, and failed iMac voice work without exposing internal tool lanes.
    - [x] Make realtime voice tool execution nonblocking so browser and work tasks do not freeze speech input or interruption handling.
    - [x] Ensure manual voice stop closes the mic session without cancelling running local work by default.
    - [x] Add a generic transcript-level voice work supervisor for browser, document, spreadsheet, PowerPoint, Markdown, visual workflow, and project/code work.
    - [x] Split long voice work into immediate spoken acknowledgement, background execution, and result delivery when ready.
    - [x] Store short acknowledgement, result summary, and detected artifact path in voice work state.
    - [x] Live-test the real xAI websocket adapter after the xAI key arrives; pre-May-25 iMac test passed with Office artifact creation by voice.
- [x] **2.2. The Mind (GPT-5.5)**
    - [x] Implement "Escalation Logic" for high-complexity strategy.
    - [x] Lock GPT usage to explicit complex cues only.
    - [x] Add GPT Plan Mode for explicit complex planning without execution.
    - [x] Add Claude pre-implementation review for GPT plans.
    - [x] Add a post-implementation Claude review hook for approved implementation workflows.
    - [x] Add controlled `/complex` dynamic workflow records with isolated research, planner, and review subagent events.
    - [x] Add bounded dynamic task graph generation for `/complex plan`.
    - [x] Add parallel subagent execution with capped 2 to 4 Gemini subagents.
    - [x] Keep `/complex` workflow status resumable through harness run/events state.
    - [x] Expand `/complex` so an approved plan can become a checkpointed agentic harness workflow.
    - [x] Persist `/complex` executable plans as structured workflow steps with owner lane, expected output, artifact refs, approval requirement, verification step, and failure policy.
    - [x] Add `/complex self-heal` as the preferred serious repair route: inspect logs, localize failure, plan repair, Claude risk review, isolated Artisan patch proposal, tests, and approval before main-repo apply.
    - [x] Add commands or natural handling for continuing, pausing, cancelling, and inspecting `/complex` agentic workflows from Telegram and iMac.
    - [x] Add regression tests proving `/complex` can create a plan-only response, create an approval-gated workflow, resume after restart, and keep repo changes isolated until approval.
- [x] **2.3. The Sight (Gemini 3.1 Flash with 3.5 Flash premium escalation)**
    - [x] Use Gemini 3.1 Flash as the primary Telegram text/research model.
    - [x] Use Gemini 3.5 Flash as the premium Sight lane and remove the old Pro branch.
    - [x] Use Gemini for Omi summarization and memory distillation.
    - [x] Add a source-aware Gemini research workflow after API keys arrive.
    - [x] Use Gemini 3.1 Flash for normal camera snapshots and escalate to Gemini 3.5 Flash only when premium sight can plausibly help.
- [x] **2.4. The Steward (Claude Opus 4.8)**
    - [x] Add the Claude Steward lane for careful review requests.
    - [x] Route natural review, critique, audit, hidden-risk, and check-this-plan prompts without adding a new command.
    - [x] Add provider readiness and smoke coverage for the Anthropic key.
    - [x] Live-test the Claude Steward lane after API keys arrive.
- [x] **2.5. The Artisan (Codex implementation lane)**
    - [x] Keep the lane name as `Artisan`; Maya should not rename it to Codex in normal user-facing flow.
    - [x] Document that Codex is the only Artisan implementation engine.
    - [x] Document that Word, Excel, PowerPoint, memory, normal chat, voice, and document review do not move to Artisan.
    - [x] Add CLI lane safety language: safe read/test/diff work is allowed, while patching, restart, deploy, delete, upload, credential, purchase, and booking actions require approval when Maya acts autonomously.
    - [x] Document the approval boundary: repo changes require Zainal approval; `~/Desktop/Maya/Projects/...` project work can be edited directly unless the action is destructive or external.
    - [x] Document that Maya must store Artisan output in the workflow desk so she can answer `what did Artisan say?`.
    - [x] Verify Codex CLI is installed on the iMac.
    - [x] Live-login/test Codex auth from Maya's service environment.
    - [x] Add a subscription-auth guard so Artisan only runs Codex when `codex login status` confirms `Logged in using ChatGPT`.
    - [x] Add an Artisan runner wrapper that calls Codex programmatically and captures structured output.
    - [x] Require Gemini to create the build brief before Artisan runs.
    - [x] Store `artisan_run_id`, Codex transcript/final-message path when available, working directory, status, summary, changed files, tests run, transcript path, artifacts, usage/cost metadata, and approval state.
    - [x] Route coding questions and code-generation requests to Artisan.
    - [x] Enforce worktree isolation for repo repairs and self-healing jobs.
    - [x] Add approval gate before applying Artisan patches to `~/projects/kampung-ai` or any other repo.
    - [x] Add direct-write support for non-destructive work inside `~/Desktop/Maya/Projects/...`.
    - [x] Add `/route`, `/cost`, workflow desk, and transcript/report support for Artisan runs.
    - [x] Add smoke tests proving Artisan jobs are queued/captured correctly.
    - [x] Add smoke tests proving repo jobs use isolated worktrees and approval does not auto-apply patches.
    - [x] Install project design skills from `emilkowalski/skill` and `Leonxlnx/taste-skill`.
    - [x] Mirror the approved app-design skill subset into local project skill folders for Artisan project use.
    - [x] Add the optional `ahujasid/blender-mcp` server entry for Codex with telemetry disabled.
    - [x] Install and enable the Blender-side MCP add-on in Blender 5.1 with telemetry consent disabled.
    - [x] Add a live Blender MCP connection test that starts the Blender-side server, confirms scene inspection/object creation through the MCP handler, and then stops the server cleanly.
    - [x] Add live Codex smoke test after login is confirmed.
    - [x] Add Blender/Maker readiness smoke and export smoke after Blender is installed.
    - [x] Add an Artisan app-project QA gate that serves the app, checks linked assets/scripts, verifies expected UI text, and records pass/fail before Maya calls app-building ready.
    - [x] Strengthen app QA with README requirement, CSS corruption checks, local HTTP smoke, and optional browser preview screenshot capture.
    - [x] Add latest-app delivery continuity so `send me the last app` returns the app path, QA summary, and Telegram zip attachment.
    - [x] Add live subscription-backed Codex app smoke proving a real app project can be created, QA checked, zipped, and delivered from the workflow desk.
    - [x] Record that app-building is an established Artisan capability that stays available and documented even when the current work session focuses on self-healing, memory, documents, or workflow reliability.
    - [x] Add an explicit approved-worktree apply-back command for repo jobs; default approval should still record permission and not silently patch the original repo.
    - [x] Add deterministic maker template selection so known simple 3D objects such as cable clips and phone stands do not wait on Codex.
    - [x] Add deterministic maker templates for label/key tags, wall hooks, and organizer trays.
    - [x] Make Maya own Blender export and validation after source generation: `.blend`, mesh export, README, and no physical print action.
    - [x] Strengthen maker QA with mesh dimensions, preview render generation, README QA notes, and Telegram delivery markers for STL, BLEND, README, and preview.
    - [x] Add latest-maker delivery continuity so `send me the last 3D model` returns path, dimensions, safety status, and attachments.
    - [x] Fix live Artisan 3D delivery timeout so a maker job completes source, `.blend`, `.stl`, and README without manual rerun.
    - [x] Add a live Artisan 3D regression that proves Gemini brief plus the Artisan maker lane produces editable Blender source, exported STL, README, route/artifact records, and no physical print action.

## ⚡ Phase 3: The Neural Link (Mudra Link - Priority)
*Goal: Use Mudra Link as a simple physical hotkey controller without making Maya depend on a direct Mudra runtime.*

- [x] **3.1. Mudra Mouse-Mode Hotkey Mapping**
    - [x] Use Mudra Link in Mouse Mode so Zainal can still navigate the iMac normally.
    - [x] Configure **Twist** in the Mudra Link app to send `Option + Space`.
    - [x] Configure **Double Twist** in the Mudra Link app to send `Option + Escape`.
    - [x] Let Maya receive only the normal iMac hotkeys; do not add a Maya-side Mudra SDK listener, WebSocket bridge, BLE listener, or gesture runtime for v1.
    - [x] Scrap the June 8 direct Mudra activation experiment.
- [ ] **3.2. Local BLE Fallback**
    - [x] Keep direct BLE/system-control ideas out of v1 unless Zainal explicitly reopens them.
- [x] **3.3. Mudra Adapter Seam**
    - [x] Keep the old event-file adapter only as a disabled research seam.
    - [x] Keep the adapter disabled by default; current v1 uses Mudra Link app hotkey mapping only.
- [ ] **3.4. Mudra Hardware Window**
    - [x] Mudra Link received and paired on June 8, 2026.
    - [x] Confirm Mouse Mode app-level mapping is the v1 direction.
    - [x] Live-test Twist opens the Maya mic and Double Twist closes it through the existing hotkey channel.
    - [x] Keep Mudra adapter disabled; June 8 direct activation attempt was scrapped.

## 🎙️ Phase 4: Ambient Memory (Omi Pendant - Priority)
*Goal: Sync 24/7 capture into Maya's memory.*

- [ ] **4.1. Tailscale Ingress**
    - [x] Configure auto-sync for Omi transcripts via Tailscale.
- [x] **4.2. The Context Sieve**
    - [x] Implement filter node to strip silence/noise from ambient feeds.
    - [x] Store distilled Omi memories in the shared memory system.
    - [x] Let Gemini own Omi transcript summarization and memory extraction.
- [x] **4.3. Omi Adapter Seam**
    - [x] Normalize `.txt` and `.json` transcript files through a dedicated adapter.
    - [x] Keep the Omi watcher optional until the hardware flow matters.
- [ ] **4.4. Omi Hardware Window**
    - [ ] Order Omi band around May 20, 2026.
    - [ ] Expect arrival and live integration window around July 1, 2026.
    - [ ] Keep Omi adapter in staging mode until the real band and transcript flow are present.

## 🗣️ Phase 5: The Voice & OS Bridge
*Goal: Make Maya speak naturally and control the iMac.*

- [x] **5.1. OS Control Bridge (`utils.py`)** - [TESTED SUCCESS]
    - [x] Add safe app inspection and richer volume controls.
    - [x] Add explicit app switching for named macOS apps.
    - [x] Add simple keyboard shortcut support for the frontmost app.
    - [x] Add typing into the frontmost app only when explicitly requested.
    - [x] Allow local folder access including Desktop through the local permission policy.
    - [x] Allow create/write file actions through chat.
    - [x] Add `app_interaction_smoke.py` for local action parsing and permission policy checks.
    - [x] Add `permission_policy_smoke.py` for file-write, Cloudflare/GCP allowance, delete/send confirmation, and private exposure denial.
    - [x] Add active iMac context extraction for frontmost app selection, including Excel, Word, PowerPoint, Chrome, and generic text fields.
    - [x] Let iMac voice inspect active selection or one-shot screen context without requiring Telegram `/screen`.
- [x] **5.2. Local Audio (`afplay`)** - [TESTED SUCCESS]
- [x] **5.3. Ara Voice Delivery**
    - [x] Shared audio rendering path for local playback and Telegram audio delivery.
    - [x] Scheduled briefings now speak aloud on the iMac.
    - [x] Lock Telegram replies to Ara voice notes once the xAI key is present.
    - [x] Send Telegram voice-note replies with `send_voice` when ffmpeg can convert Ara audio to Opus.
    - [x] Keep Telegram text-only before the xAI key rather than sending the wrong local fallback voice.
- [ ] **5.4. Local iMac Voice Loop**
    - [x] Capture microphone speech on the iMac.
    - [x] Resolve local speech inputs by device name instead of fixed changing macOS indexes.
    - [x] Prefer `Zainal’s Headphone` as the named speech input and keep `iMac Microphone` as fallback.
    - [x] Disable voice wake activation for live use so idle listening is not needed.
    - [x] Remove Whisper from the live wake path because voice wake activation is scrapped.
    - [x] Keep Whisper only as an inactive fallback for one-shot transcription and offline debugging.
    - [x] Archive openWakeWord work as an experiment, not a future live trigger.
    - [x] Do not test openWakeWord for live voice activation unless Zainal explicitly reopens it later.
    - [x] Record Zainal-specific positive wake samples and negative background samples.
    - [x] Archive old sample recorder experiment outside the live path.
    - [x] Archive old local scorer prototype outside the live path.
    - [x] Improve the scorer beyond the first 85 percent leave-one-out baseline before live use.
    - [x] Add a two-stage wake probe: local candidate score first, tiny STT confirmation second.
    - [x] Confirm the two-stage wake path before connecting it to live Maya.
    - [x] Skip openWakeWord live hardening because voice wake activation is scrapped.
    - [x] Do not connect openWakeWord to Maya live path.
    - [x] Keep the iMac voice channel disabled while the wake detector is being redesigned.
    - [x] Add hotkey voice channel so `Option + Space` starts Maya without always-on mic capture.
    - [x] Add `Option + Escape` manual stop for the hotkey voice session.
    - [x] Keep microphone capture closed until the hotkey starts a voice session.
    - [x] Prove hotkey can trigger the Grok Voice Agent path.
    - [x] Do not continue natural voice testing on the `ffmpeg` file-capture hotkey loop.
    - [x] Rebuild hotkey voice as realtime streaming before the next serious iMac voice test.
    - [x] Use Grok Voice Agent speech-to-speech for the long-term iMac conversation path.
    - [x] Escalate to GPT-5.5 only when needed.
    - [x] Speak replies locally through the iMac speakers with Ara.
    - [x] Set the wake window to 5 seconds so live voice does not stay open after silence.
    - [x] Let the iMac channel hand wake-session turns to the bounded Grok Voice Agent manager when enabled.
    - [x] Add durable iMac voice session transcript logging for user speech, Maya speech, tool calls, interruptions, and diagnostics.
    - [x] Export iMac voice session review logs as Markdown under `Desktop/Maya/voice_sessions`.
    - [x] Add voice session review commands for last session, today's sessions, search, export, and diagnostics.
    - [x] Add `voice_session_log_smoke.py` and include it in launch rehearsal.
    - [x] Remove wake detection from live voice path. Manual trigger only.
- [x] **5.5. No Call Mode v1**
    - [x] Remove Loopback and virtual call audio routing after live test showed quality and stability issues.
    - [x] Remove call context tools from iMac realtime voice.
    - [x] Remove call listening and call-note behavior from local iMac voice.
    - [x] Keep Maya as normal iMac voice only when Zainal is on WhatsApp or FaceTime.
    - [x] Instruct Maya not to claim she can join, listen to, privately monitor, route audio into, or summarize calls.

## 👁️ Phase 6: Senses & AR
*Goal: Give Maya eyes through the approved external camera only.*

- [ ] **6.1. MediaPipe Vision (`vision.py`)**
    - [x] Block built-in iMac camera index 1 by default.
    - [x] Default Maya vision to Cisco Desk Camera 4K index 0.
    - [x] Add external camera open-event adapter for iMac activation.
    - [x] Register Cisco Desk Camera 4K as Maya Eye.
    - [x] Confirm Cisco Desk Camera 4K is video index 0 and FaceTime HD Camera is video index 1.
    - [x] Add blocked lens detection for black frames and flat low-light shutter frames.
    - [x] Add `camera_probe.py` for Cisco-only vision checks.
    - [x] Confirm Terminal Python/OpenCV probe can read Cisco frames when the physical privacy block is open.
    - [x] Gate live camera opening so Telegram-only mode does not quietly use Maya Eye.
    - [x] Add `vision_probe.py` for short Cisco-only `VisionNode` loop checks.
    - [x] Confirm `vision_probe.py` sees Cisco frames when the physical block is open.
    - [x] Confirm Cisco physical privacy block produces no sight.
    - [x] Make `/see` toggle camera guidance on or off and make `/closeimac` close the local preview.
    - [x] Capture one safe Cisco frame for guided visual help.
    - [x] Route visible frames to the vision model for practical step-by-step guidance.
    - [x] Default vision snapshots to Gemini 3.1 Flash, with Gemini 3.5 Flash escalation for blurry labels, tiny text, risky hardware questions, low confidence, or explicit careful review.
    - [x] Support clean visual marks: circles for exact points, rectangles for areas, and one grouped rectangle when many circles would be messy.
    - [x] Apply calibrated desk orientation so Maya answers from Zainal's side, not camera side.
    - [x] Report honestly when vision is disabled, not in iMac work location, permission blocked, or privacy block closed.
    - [x] Add `vision_command_smoke.py` for command behavior.
    - [x] Add `vision_answer_probe.py` for Terminal end-to-end camera plus vision model checks.
    - [x] Confirm launchd or final app runtime can read Cisco frames.
    - [x] Camera can detect presence.
- [x] **6.2. Screen Sight**
    - [x] Add snapshot-based iMac screen capture through macOS `screencapture`.
    - [x] Keep screen sight separate from Cisco camera sight.
    - [x] Add `/screen` as a toggle for persistent remote screen sight from Telegram.
    - [x] Remove `/screen off` as a public control because `/screen` is the toggle.
    - [x] Keep `/closeimac` shutdown behavior for screen sight.
    - [x] Support `/screen question` for one-shot Telegram screen questions.
    - [x] Support natural iMac phrases like `look at my screen` and `explain this slide`.
    - [x] Route screen snapshots through Gemini 3.1 Flash with Gemini 3.5 Flash escalation for tiny text, complex diagrams, low confidence, or careful review.
    - [x] Record last screen sight status for `/status`.
    - [x] Add `screen_command_smoke.py` for no-key screen sight behavior.
    - [x] Keep screen follow-ups like Safari, Codex, and open-app questions on the screen sight route.
    - [x] Keep work-context follow-ups like `what about now` and `should I put this here` on the screen sight route while `/screen` is active.
    - [x] Use macOS app state for open-app questions instead of visual guessing from Dock indicators.
    - [x] Let named-app content questions bring the app forward before the screen snapshot when the app is running.
    - [x] Keep iMac active context selection-first before screen snapshot for current-work questions.
    - [x] Keep Telegram screen access explicit through `/screen` and `/screen question`.

## 🧭 Phase 7: Visual Workflows & CLI Artifacts
*Goal: Let Maya create real rendered workflow visuals and keep artifact work local-first.*

- [x] **7.1. Visual Workflow Renderer**
    - [x] Add `map this idea visually`, `workflow diagram`, `architecture diagram`, `flow diagram`, and `Mermaid visual` commands.
    - [x] Save Mermaid source and rendered SVG under `Desktop/Maya/architecture`.
    - [x] Open rendered visuals on iMac and attach them on Telegram.
    - [x] Use Mermaid CLI when available and a built-in SVG fallback otherwise.
- [x] **7.2. Artifact-First Work**
    - [x] Keep Word, PowerPoint, Excel, Markdown, and visual workflow creation in CLI/file tooling first.
    - [x] Use native apps for review and repair rather than manual creation.
    - [x] Resolve app aliases like Chrome to Google Chrome before deciding whether an app is open.
    - [x] Return a clear closed-app answer when a named app is not in the macOS running app list.
    - [x] Add `screen_probe.py` for runtime Screen Recording permission checks.

## 📈 Phase 8: Evolution
- [x] **8.1. Memory Migration** - [COMPLETED 169 HIGH-VALUE CHUNKS]
- [x] **8.2. Weekly Reflection (Sunday 20:00)**
    - [x] Schedule and deliver weekly reflection through the routine runtime.
    - [x] Add a launchd weekly memory job for Sunday 20:00 using the documented reflection cadence.
    - [x] System Health Heartbeat logic.
- [ ] **8.3. Unified Memory**
    - [x] Merge iMac, Telegram, and Omi interactions into one shared memory model.
    - [x] Prioritize direct interactions over ambient memory.
    - [x] Add a no-key weekly memory dry-run pass for iMac, Telegram, and Omi-ready storage.
    - [x] Save prepared weekly summaries into local weekly summary storage.
    - [x] Make Sunday reflection read the prepared weekly summary instead of processing raw logs live.
    - [x] Add `weekly_memory_smoke.py` and include it in launch rehearsal.
    - [x] Add shared `session_summaries` storage for Codex-style context compaction.
    - [x] Add a no-key session compactor for older shared iMac and Telegram history.
    - [x] Make session compaction token-aware internally so context lasts longer than the old small message-count window.
    - [x] Save topic-scoped summaries so separate conversations do not collapse into one blurred thread.
    - [x] Preserve hard facts in `context_facts`, vibes/themes in `context_vibes`, and lossy summaries in `session_summaries`.
    - [x] Inject the latest relevant compacted session context into Maya's prompt path.
    - [x] Add `/context` and natural context-window inspection.
    - [x] Add `session_compactor_smoke.py` and include it in launch rehearsal.
    - [x] Add `memory_soak_smoke.py` to verify long no-key conversation compaction preserves context, facts, and preferences.
    - [x] Add `/memory` source and confidence inspection.
    - [x] Add `/forget` for specific memory removal.
    - [x] Add `/memorycleanup` for stale compacted context cleanup.
    - [x] Add Hermes style `maya_core_memory` capped at 2477 characters.
    - [x] Add Hermes style `zainal_profile_summary` capped at 1499 characters.
    - [x] Add SQLite FTS5 session search for old normal sessions.
    - [x] Save safe iMac voice session summaries after hotkey sessions end.
    - [x] Add manual `save this conversation for memory` session checkpoint.
    - [x] Add `memory_control_smoke.py` and include it in launch rehearsal.
    - [x] Let Gemini 3.1 Flash summarize weekly raw logs and remove conversational noise.
    - [x] Let Gemini 3.5 Flash handle premium weekly synthesis when the week is dense, ambiguous, or needs stronger language quality.
    - [x] Let Claude review weekly memory candidates for overreach, false assumptions, vague preferences, and unsafe memory.
    - [x] Use GPT-5.5 only for high-value weekly memory shaping when the summary needs stricter judgement.
    - [x] Promote dry-run weekly facts into local preferences, lessons, and tasks after provider review is available.
    - [x] Keep preferences separate from event memory.
    - [x] Retrieve relevant preferences, tasks, and long-term memory before replying.
    - [x] Filter operational/internal values like chat ids out of user-facing memory retrieval.
    - [x] Keep preference questions scoped to the preference layer instead of broad keyword-based archive search.
    - [x] Keep archive/project lore disabled by default for this new project.
    - [x] Clear legacy archive/state so this project starts from a fresh memory baseline.
    - [x] Prevent personality drift from ambient transcripts alone.
- [ ] **8.4. Quantum Experiments**
    - [x] Keep Quantum Leaf outside live routing until corrected smoke tests prove it is reliable.
    - [x] Fix the Quantum Leaf smoke test so mixed-route expectations are actually checked.
    - [x] Add a deterministic quantum advisory layer for themes, vibes, hidden links, and "how should I think" framing.
    - [x] Keep the quantum layer out of dates, tasks, permissions, security, costs, money, delete, send, booking, and exact-rule paths.
    - [x] Make the advisory layer disableable by `ENABLE_QUANTUM_ADVISORY`.
    - [x] Block quantum advisory output from overriding `/complex`, coding-to-Artisan, current-news, vision, screen, commands, learning, safety, or permission routes.
    - [x] Add `quantum_advisory_smoke.py` and include it in launch rehearsal.
    - [ ] Test normal embeddings before any GCP tensor-network or PennyLane cloud path.
- [ ] **8.5. Meeting Bot API Research**
    - [ ] Keep this out of Phase 7. Finish normal assistant reliability first.
    - [ ] Evaluate Google Meet as the first proper call-mode target instead of WhatsApp/FaceTime audio routing.
    - [ ] Compare meeting bot providers such as Recall.ai and MeetStream for real participant join, transcript/audio streaming, output media, cost, privacy, and consent requirements.
    - [ ] Prototype only after Phase 7 evidence says Maya is stable as a normal assistant.
    - [ ] Preserve the v1 doctrine: no WhatsApp/FaceTime call mode, no Loopback-only call feature, and no claim that Maya can privately join or summarize calls.

## 📡 Phase 9: Channel Integration
*Goal: Make every channel feel like one Maya.*

- [ ] **9.1. Telegram as Secondary Channel**
    - [x] Use Gemini as the default Telegram text/research channel.
    - [x] Strip internal channel tags from Telegram replies.
    - [x] Shape Telegram text so Maya sounds warm and natural instead of like a status report.
    - [x] Prefer a fast Gemini-first path for simple Telegram chat; reserve heavier orchestration for more complex requests.
    - [x] Split only clear multi-question Telegram prompts, while preserving outline examples and structure lessons as one message.
    - [x] Add Telegram audio reply plumbing for Maya speech.
    - [x] Split long Telegram text replies into multiple Bot API messages without needing Telegram Premium.
    - [x] Attach generated files such as `.docx` and `.pptx` to Telegram replies through the delivery layer.
    - [x] Add `telegram_delivery_file_smoke.py` and include it in launch rehearsal.
    - [x] Reduce visible Telegram slash shortcuts to `/help`, `/status`, `/imac`, `/see`, `/screen`, `/project`, `/memory`, and `/complex`.
    - [x] Keep older Telegram slash commands as hidden compatibility aliases.
    - [x] Add Telegram slash shortcuts for memory source, forget, memory cleanup, and self-heal inspection.
    - [x] Add `/complex` as the only official Telegram route to GPT-5.5.
    - [x] Make `/complex` and explicit iMac complex cues use GPT-5.5 with `medium` reasoning effort.
    - [x] Add `/cost` as a direct Telegram usage estimate command.
    - [x] Add `/providers` as a direct Telegram provider-readiness checklist.
    - [x] Add `/route` as a direct Telegram routing-inspection command.
    - [x] Add `/context` as a direct Telegram compacted-context inspection command.
    - [x] Add `/selfheal` as a direct safe repair-proposal command.
    - [x] Add `/weekly` and natural weekly-reflection phrasing that reads the prepared weekly summary.
    - [x] Block normal Telegram text from falling through to any auto GPT-5.5 deep-routing path.
    - [x] Route incoming Telegram voice notes through transcription and then the normal Telegram routing path.
    - [x] Do not force English for xAI STT on Telegram voice notes.
    - [x] Route incoming Telegram photos through a dedicated photo handler instead of ignoring photo-only messages.
    - [x] Download the largest Telegram photo variant and send it to Gemini Flash vision with the caption as user intent.
    - [x] Record Telegram photo route/cost as `photo` plus `Gemini Flash sight`.
    - [x] Add smoke coverage for Telegram photo download, caption prompt, privacy boundary, and vision handoff.
    - [x] Force Malay or Manglish Telegram answers through Gemini before Ara speaks them.
    - [x] Keep Telegram voice as Ara voice notes instead of Grok Voice Agent sessions.
    - [x] Make Telegram Ara voice replies the locked default, with text-only fallback until the xAI key exists.
    - [x] Live-test Telegram Ara voice-note replies against the xAI API.
- [ ] **9.2. Shared Runtime Across Channels**
    - [x] Reuse the same routing and memory context path for iMac and Telegram.
    - [ ] Keep channel adapters thin so the brain stays centralized.
    - [ ] Preserve one Maya identity across Grok, Gemini, GPT-5.5, The Steward, and The Artisan.
    - [x] Carry only a short recent-topic window for Telegram follow-ups instead of dragging the full chat forever.
    - [x] Carry a compacted shared session context across iMac and Telegram.
    - [x] Support an explicit `new topic` reset for conversational context.
    - [x] Support Telegram activation commands: `open iMac` and `change work location to iMac`.

## 🧩 Phase 10: Host Identity
*Goal: Move Maya from a development shell into a real system identity.*

- [ ] **10.1. Development Host**
    - [ ] Run Kampung AI from Terminal during active development.
    - [ ] Grant Terminal the permissions needed for current testing.
- [ ] **10.2. Dedicated Runtime Identity**
    - [ ] Define the long-term host as a dedicated app/service instead of Terminal.
    - [ ] Move microphone, automation, and startup permissions to the final host identity.
    - [x] Make Kampung AI feel more like an appliance via a `launchd` background service.
    - [x] Install the `launchd` plist into `~/Library/LaunchAgents`.

## 🪞 Phase 11: Maya Identity
*Goal: Keep Maya feeling like one person across every channel.*

    - [x] **11.0. Visual Identity**
    - [x] Choose **Living Bamboo** as the wrapper/app logo direction.
    - [x] Save the approved source image to `assets/brand/kampung-ai-living-bamboo.png`.
    - [x] Render a high-resolution 4096 x 4096 raster export at `assets/brand/kampung-ai-living-bamboo-upscaled-4096.png`.
    - [x] Reject and archive the first SVG draft because it did not preserve the approved logo's organic feel.
    - [x] Lock the visual reasoning: local, alive, warm, trusted, and quietly intelligent.
    - [x] Avoid generic AI visuals such as robots, chat bubbles, AI brains, neon cyber motifs, purple gradients, and obvious circuit-board styling.
    - [ ] Create a proper vector redraw later with a design tool or better tracing workflow before the real app wrapper is packaged.
    - [ ] Fine-tune the final app icon after the macOS wrapper shape and iconset requirements are known.
- [ ] **11.1. Tone**
    - [ ] Keep Maya warm, direct, and lightly playful.
    - [ ] Avoid corporate phrasing and provider-name leakage.
    - [x] Stop global provider redaction on personal Telegram and iMac replies so visible app names can be named.
    - [x] Keep stricter redaction for external outbound delivery such as GitHub, email, WhatsApp, public webhooks, or shared reports.
- [ ] **11.2. Response Style**
    - [ ] Keep iMac replies short and spoken-friendly.
    - [x] Let Telegram replies carry more context when useful without leaking internal tags or support scaffolding.
    - [x] Ignore wake-name prefixes like `Maya,` so direct Telegram commands still match correctly.
    - [x] Ignore normal trailing punctuation on direct state questions so `what is my preference?` still hits the exact command path.
    - [x] Keep Telegram state-based replies natural, not mechanical, even when they come from tasks/routines/preferences instead of the model.
    - [x] Avoid canned intros for bundled Telegram replies; grouped answers should just answer.
    - [x] Add a response-policy layer for broad identity/channel/system questions instead of patching one-off phrasings forever.
    - [x] Route identity, capability, goal, and roadmap questions through curated profiles before model/legacy memory.
    - [x] Enforce stored formatting preferences like "no dash symbol" or "no exclamation mark" as a final reply-style pass.
    - [x] Teach Maya a concise Manglish style for Malay/Manglish replies instead of defaulting to formal or padded Malay.
    - [x] Detect teaching or correction input and treat it as guidance instead of replying to the sample content.
    - [x] Use explicit learning cues: `I am teaching you`, `My preference`, and `Remember`.
    - [x] Replace manual memory seeding with a runtime-owned learning pipeline.
    - [x] Auto-save explicit lessons after write and read-back verification.
    - [x] Ask for confirmation before saving implicit lessons.
    - [x] Keep a lesson log separate from final preference rules.
    - [x] Support lesson inspection with recent learned rules.
    - [x] If the lesson log is empty but preferences exist, answer honestly with saved preferences instead of pretending nothing is known.
    - [x] Route bundled Telegram lesson questions through the learning pipeline instead of model fallback.
    - [x] Retrieve logged lessons into the prompt path so learned behavior is reused.
    - [x] Use `1)` for main points and `a)`, `b)`, `c)` for subpoints when structured answers help.
    - [x] Treat stories and `cerita` differently from structured answers; they should flow like a short essay when that is the learned preference.
    - [x] Store story rhythm as its own preference, not just the broad "essay not points" rule.
    - [x] Keep improvement and roadmap answers grounded in the current personal scope of Kampung AI.
    - [x] Mirror Zainal's current language: English gets English, Malay/Manglish gets Malay/Manglish.
    - [ ] Reserve deeper analysis for explicit escalation.
- [ ] **11.3. Personality Stability**
    - [ ] Keep Maya's core personality curated and stable.
    - [ ] Let Gemini suggest or apply small preference updates without rewriting Maya's identity.

## 🤖 Phase 12: Bounded Agency
*Goal: Make Maya agentic without becoming messy or unsafe.*

- [x] **12.1. Task Store**
    - [x] Add persistent tasks with status, due time, result, and error state.
    - [x] Keep task memory separate from raw conversation history.
- [x] **12.2. Preference Store**
    - [x] Add a dedicated preference table for stable user habits and notes.
- [x] **12.3. Autonomy Policy**
    - [x] Define bounded autonomy modes (`observe`, `suggest`, `auto_safe`, `full`).
    - [x] Allow create/write file work and configured Cloudflare/GCP use.
    - [x] Keep delete and send/share actions confirmation-gated.
    - [x] Hard-block private exposure of bank details, passwords, OTPs, API keys, tokens, secrets, private keys, and recovery phrases.
    - [x] Add pattern-based secret detection for common key shapes, private key headers, card-like numbers, and OTP phrases.
    - [x] Add `secret_detection_smoke.py`.
- [x] **12.3a. Codex Style Project Mode**
    - [x] Resolve projects by name from `/Users/zainalabidinjamal/projects`, `~/Desktop/Maya/Projects`, and legacy `~/Downloads/Kampung AI/Projects`.
    - [x] Persist one active project across Telegram and iMac until Zainal closes or switches it.
    - [x] Let follow-ups like `make a README for this project` use the active project.
    - [x] Ask when project matches are ambiguous instead of guessing.
    - [x] Save ambiguous project choices and accept numbered replies like `1` or `2`.
    - [x] Keep `new topic` from clearing the active project.
    - [x] Block `this project` file/document writes when no active project exists.
    - [x] Store project memories separately from personal memory.
    - [x] Add `project_mode_smoke.py`.
- [x] **12.4. Background Runtime**
    - [x] Start a polling agent runtime alongside the channel adapters.
    - [x] Claim and process due tasks in the background.
- [x] **12.5. First Safe Actions**
    - [x] Deliver local follow-up reminders.
    - [x] Support short history summaries as safe autonomous work.
- [x] **12.6. Planner / Verifier Loop**
    - [x] Add explicit plan-step verification instead of one-shot task execution.
    - [x] Persist workflow runs and step context into `workflow_runs`.
    - [x] Resume running multi-step tasks from the last saved step after restart or crash.
    - [x] Add `workflow_persistence_smoke.py`.
- [x] **12.7. Channel Delivery**
    - [x] Deliver due tasks through Telegram as well as local iMac notifications.
- [x] **12.8. Natural Task Capture**
    - [x] Support creating simple tasks from conversation.
    - [x] Support listing open tasks and stored preferences.
    - [x] Support cancelling/removing open tasks from conversation.
    - [x] Prevent task-command replies from re-answering previous Telegram questions.
    - [x] Expand due-date parsing beyond simple relative phrases.
- [x] **12.9. Conversational Confirmations**
    - [x] Keep sensitive approvals in plain chat, not inline buttons.
    - [x] Let `yes`, `no`, `later`, and `cancel` resolve the latest pending action.
    - [x] Accept natural confirmation wording like `no that is okay` instead of requiring exact one-word replies.
    - [x] Support approval-gated Telegram sends as the first sensitive action.
    - [x] Return a local no-pending response when `yes` or `no` arrives with nothing waiting for approval.
    - [x] Prevent loose confirmations from falling through to provider calls.
- [x] **12.10. Skill Registry**
    - [x] Define Maya's built-in skill list with safety and approval metadata.
    - [x] Surface skill listing in chat so Maya can explain what she can do.
    - [x] Inject relevant skill context into the reply path.
    - [x] Add bounded browser, Office document, travel research, and checkout-guard skills.
    - [x] Add `browser_capability` as the parent iMac browser route.
    - [x] Keep child browser skills explicit: `general_browser`, `google_search`, `google_images`, `flight_search`, `youtube_research`, `reddit_research`, `google_cloud_console`, `booking_com_hotel_search`, `airbnb_stay_search`, and `frequent_site_open`.
    - [x] Add executable site skills for Google Search, YouTube, Reddit, and Google Cloud Console.
    - [x] Add a frequent-site registry for common iMac sites with category-specific safety policy.
    - [x] Keep finance sites such as Maybank open-only with hard blocks for credentials, OTPs, card data, account data, payment forms, and private financial data.
    - [x] Add Sight Research and Steward Review as built-in skills.
    - [x] Add a provider capability registry for lane owners, tools, boundaries, cost tier, routing triggers, memory rights, and execution rights.
    - [x] Keep provider-native capabilities behind Maya's safety gates and skill lifecycle.
- [x] **12.11. Bounded Skill Creation**
    - [x] Let Maya draft a new skill scaffold when she detects a gap.
    - [x] Store skill proposals and local scaffold files for review.
    - [x] Keep activation bounded behind human approval.
    - [x] Detect unsupported action requests and ask before drafting a missing skill.
    - [x] Prevent unsupported actions from falling through to model chat and pretending completion.
    - [x] Add skill-learning lifecycle states: draft, proposed, approved, active, and disabled.
    - [x] Add scaffold sections for trigger phrases, inputs, outputs, required tools, permissions, safety, tests, and activation checklist.
    - [x] Keep web research as a scaffold section for now, not automatic external-code adoption.
    - [x] Add skill lifecycle commands for showing, editing, approving, activating, and disabling skills.
    - [x] Keep proposed and disabled skills out of active prompt context.
    - [x] Create skill scaffolds immediately after chat approval.
    - [x] Log active skill usage with selected skill, query, and reason.
    - [x] Add `skill_usage_smoke.py`.
    - [x] Add `unsupported_action_smoke.py` so the guardrail is tested.
    - [x] Add `hardening_flow_smoke.py` for no-pending confirmations, project choice, this-project guardrails, and skill lifecycle.
- [x] **12.12. Scheduled Routines**
    - [x] Add a dedicated routine store for recurring schedules.
    - [x] Support morning briefing, evening recap, and weekly reflection.
    - [x] Let routines enqueue safe briefing tasks for the agent runtime.
    - [x] Support chat commands to create, list, and disable routines.
    - [x] Clarify that briefings should be natural chat triggers, not command-first workflows.
- [x] **12.13. Go-Live Smoke Test**
    - [x] Add a one-command provider smoke test for Gemini, GPT-5.5, Claude, Grok, Ara TTS, and xAI STT.
    - [x] Add Codex/Artisan readiness smoke once Codex is installed.
    - [x] Make the smoke test fail gracefully when keys or the correct interpreter are missing.
    - [x] Load `.env` directly so launch key checks do not depend on shell sourcing.
    - [x] Count Ara TTS only when the xAI API path works, not when macOS fallback creates audio.
    - [x] Use neutral smoke phrases so provider-name masking does not create false failures.
    - [x] Add `delivery_redaction_smoke.py` so personal channels preserve app names while external destinations redact.
- [x] **12.14. Go-Live Rehearsal**
    - [x] Add a reusable no-key rehearsal script for routines, approvals, local actions, and health.
    - [x] Confirm the rehearsal runs cleanly under the project venv.
    - [x] Add `may1_rehearsal.py` as the one-command local launch rehearsal runner.
- [x] **12.15. Runtime Health**
    - [x] Add rotating runtime and error logs.
    - [x] Add a heartbeat snapshot file for quick diagnosis.
    - [x] Teach `doctor.py` to report service and runtime status.
    - [x] Suppress noisy provider polling logs and redact secrets from log output.
- [x] **12.16. May 20 Launch Readiness**
    - [x] Add `MAY_1_LAUNCH_RUNBOOK.md` for live-key day.
    - [x] Update live-key day to May 20, 2026.
    - [x] Add `learning_smoke.py` so Maya's own learning pipeline can be checked without live provider keys.
    - [x] Keep the launch sequence conservative: text first, provider smoke next, voice last.
    - [x] Split live provider smoke into strict text, vision, and voice gates.
    - [x] Add `provider_readiness.py` and `provider_readiness_smoke.py`.
    - [x] Add `provider_capabilities_smoke.py`.
    - [x] Add local usage tracking so `/cost` can show estimated spend by lane.
    - [x] Add route tracking so `/route` can show the last lane, reason, input type, and cost flag.
    - [x] Add self-heal proposal storage and `self_healing_smoke.py`.
    - [x] Make self-heal proposal-first with detect, isolate, smallest-patch direction, exact tests, and approval before code changes.
    - [x] Prevent self-heal from deploying or restarting Maya without approval.
    - [x] Add golden conversation evals for tone, memory, context, task capture, and command mapping.
    - [x] Add hardware readiness smoke for Omi, deliberate hotkeys, wake-window removal, and permission boundary.

## 🧱 Phase 13: Engineering Discipline
*Goal: Keep Kampung AI easy for Zainal, Codex, and The Artisan to understand.*

- [x] **13.1. Code Size Rule**
    - [x] Keep each `.py` file under 300 lines.
    - [x] Treat 250 to 280 lines as an early refactor warning.
- [x] **13.2. Module Responsibility Rule**
    - [x] Keep each file responsible for one clear thing.
    - [x] Avoid splitting code just for the sake of splitting.
    - [x] Extract only at real boundaries that improve readability or reduce confusion.
    - [x] Extract channel routing decisions from `assistant.py` into `assistant_routes.py`.
- [x] **13.3. Enforcement**
    - [x] Inject the 300-line engineering rule into The Artisan prompt path.
    - [x] Add `code_health.py` to report warnings, urgent refactors, and violations.
    - [x] Add code-health output to `doctor.py`.
    - [x] Refactor risky files so no `.py` file is currently in the 280-line warning band.
    - [x] Extract Telegram help/status/voice helpers so `telegram_commands.py` leaves the 250-line warning band.

## 🖥️ Phase 14: iMac App Body
*Goal: Let Maya use the iMac like a capable local partner while keeping money and privacy guarded.*

- [x] **14.1. Browser Research Boundary**
    - [x] Add a browser-search action path for explicit web and flight research requests.
    - [x] Let Maya open searches for flights, prices, dates, airlines, baggage, and timing.
    - [x] Keep booking, purchases, payments, uploads, and form submissions confirmation-gated.
    - [x] Parse natural app phrases like `open my chrome`, `open chrome in my imac`, and `open it in my imac`.
    - [x] Add full assistant-path smoke coverage for Maya-prefixed, polite, browser-alias, and pronoun app commands.
    - [x] Make app opening behave like a person opening an app: launch it, create or raise a browser window, and verify it is frontmost.
    - [x] Answer short follow-ups like `where?` from app-control state instead of falling through to the model.
- [x] **14.2. Browser Interaction Loop**
    - [x] Let Maya inspect the active Chrome page text after opening a search.
    - [x] Add guided click handling for visible non-sensitive browser targets.
    - [x] Add post-click browser verification by inspecting the page after a click.
    - [x] Ask before sensitive browser clicks such as booking, checkout, payment, purchase, submit, passport, or card entry.
    - [x] Add smoke tests for browser control, workflow page inspection, safe clicks, and sensitive-click approval.
    - [x] Keep a persistent browser task state with goal, query, and recent steps.
    - [x] Add active follow-up handling for cheaper, earlier, later, date, baggage, and filter changes.
    - [x] Add simple non-sensitive browser form filling by visible field label or placeholder.
    - [x] Combine DOM page inspection, clickable/fillable target inspection, and screen-capture availability in browser inspection replies.
    - [x] Add smoke coverage for browser DOM plus screen-grounding availability.
    - [x] Add structured browser-agent state for task type, URL, title, query, filters, compared options, confidence, retry count, estimated cost, and pending sensitive action.
    - [x] Add a cost-safe browser policy that keeps local DOM and screen paths free, gates Gemini Flash and Pro browser-understanding calls, and keeps Claude/GPT out of normal browser execution.
    - [x] Strengthen browser click verification with DOM text hash, modal markers, target presence, URL, and title.
    - [x] Store browser observations as structured harness evidence with URL, title, text hash, click/fill targets, screen status, confidence, and provenance.
    - [x] Add `browser_agent_maturity_smoke.py` for dynamic-page verification, cost gates, browser state, and sensitive-click pause behavior.
    - [x] Add Maya Chrome extension bridge with token-gated localhost WebSocket, named Maya tab group, badge status, page text, screenshot, and tab cleanup.
    - [x] Port browser click, fill, element, result-option, price-result, and ranked-result controls to the Maya Chrome extension path.
    - [x] Add a browser driver selector that prefers the Maya Chrome extension when connected and falls back to AppleScript when it is not.
    - [x] Add offline bridge smoke coverage for extension request correlation, token auth, page parsing, click/fill controls, screenshots, cleanup, error, and timeout paths.
    - [x] Run live Maya Chrome extension reliability nights with the unpacked extension loaded; `night2` reached 95%, `night3-rerun` reached 91.7%, and `night4_extension_rerun` reached 96.7%, all with 10/10 safety stops and zero criticals.
    - [x] Audit `night4_extension_rerun` browser evidence: 58 browser-opening steps used extension tabs and zero `open_url` steps escaped to AppleScript or ungrouped Chrome tabs.
    - [x] Make live browser reliability runs use the Maya Chrome extension driver by default so proof tabs open under the `Maya` tab group; AppleScript runs must be explicitly marked as legacy baselines.
- [x] **14.3. Office Work**
    - [x] Add general document creation v1 for Markdown, Word, and PowerPoint drafts.
    - [x] Put Markdown notes under `~/Desktop/Maya/notes`.
    - [x] Put Word drafts under `~/Desktop/Maya/documents`.
    - [x] Put PowerPoint drafts under `~/Desktop/Maya/presentations`.
    - [x] Put Excel drafts under `~/Desktop/Maya/spreadsheets`.
    - [x] Add general Excel `.xlsx` creation v1 for trackers, comparisons, and simple tables.
    - [x] Put `this project` Markdown and Word drafts under the active project's `docs` folder.
    - [x] Support v1 Markdown append/update when the target is clear.
    - [x] Let Maya create a starter PowerPoint deck from structured chat instructions.
    - [x] Record artifact-first PowerPoint creation: create editable `.pptx` directly, open it in PowerPoint for review, and avoid click-building every slide unless UI repair is needed.
    - [x] Let Maya create a general Word draft beyond network troubleshooting.
    - [x] Send generated Office files back through Telegram when the request comes from Telegram.
    - [x] Open generated documents locally when the request comes from the iMac.
    - [x] Add `document_actions_smoke.py` and include it in launch rehearsal.
    - [x] Add `/edit` and natural `edit` routing for latest-document refinement across Telegram and iMac.
    - [x] Add natural latest-Word edit routing for follow-ups like `update that to 4 days`; update the latest `.docx` in place by default, keep an internal hidden backup, restore on QA failure, and create a visible new version only when Zainal asks for a copy/new version.
    - [x] Let Maya edit existing Word documents from structured chat instructions.
    - [x] Let Maya edit existing PowerPoint decks from structured chat instructions.
    - [x] Let Maya edit existing Excel workbooks from structured chat instructions.
    - [x] Ensure edit workflows create a safe new version or update in place only when appropriate, then rerun artifact QA.
    - [x] Add PPTX visual QA before Maya calls PowerPoint output polished.
    - [x] Render created or revised PPTX files and check for placeholder text, ellipsis overflow, truncated copy, missing readable text, and render count mismatch.
    - [x] Add one bounded PPTX auto-revision pass before delivery.
    - [x] If PPTX QA still fails, make Maya call it a draft with known issues instead of polished output.
    - [x] Add PPTX polish grade: draft-level, good, or strong.
    - [x] Detect repeated slide titles and incomplete sentence meaning in PPTX polish review.
    - [x] Let Claude provide a presentation polish grade after local QA passes.
    - [x] Add equivalent visual QA before Maya calls Word output polished.
    - [x] Use Word and PowerPoint as normal iMac apps when that is more natural than a separate UI.
- [x] **14.4. Workspace Creation**
    - [x] Create folders under `~/Desktop/Maya` by default.
    - [x] Create projects under `~/Desktop/Maya/Projects` by default.
    - [x] Add starter `docs`, `src`, `assets`, and `README.md` for new projects.
- [x] **14.5. Drawing and Image Output**
    - [x] Create simple local SVG drawings under `~/Desktop/Maya/drawings`.
    - [x] Send drawing files in Telegram and open them on the iMac depending on the active channel.
    - [x] Add an optional Gemini image-generation path through `GEMINI_IMAGE_MODEL` and `ENABLE_GEMINI_IMAGE_GENERATION`.
    - [x] Add `workspace_drawing_smoke.py` and include it in launch rehearsal.
- [x] **14.6. Travel Booking Skill**
    - [x] Keep flight research as an active workflow so date or cheaper-option follow-ups update the browser search.
    - [x] Turn flight research into a guided browser flow with persistent search, compare, filter, click, and fill steps.
    - [x] Support compare first, choose exact option second, confirm purchase last.
    - [x] Block card, bank, passport, password, OTP, token, and API-key exposure.
- [x] **14.7. Network Troubleshooting Workflow**
    - [x] Run basic safe local network checks.
    - [x] Create a Word troubleshooting note for lengthy results.
    - [x] Open the generated document in Word for review.
    - [x] Add `imac_workflows_smoke.py` for flight, presentation, and network workflow coverage.
- [x] **14.8. Default Output Location**
    - [x] Put Maya-created workflow files under `~/Desktop/Maya` unless Zainal specifies another folder.
    - [x] Make simple relative file writes default to `~/Desktop/Maya`.
    - [x] Keep legacy `~/Downloads/Kampung AI` generated files readable and sendable.

## 🧭 Phase 15: Maya Agent Harness
*Goal: Make Maya's work persistent, resumable, and inspectable through local LangGraph checkpoints.*

- [x] **15.1. Local LangGraph Core**
    - [x] Add harness state, store, graph, tools, and router modules.
    - [x] Use local SQLite checkpointing through LangGraph.
    - [x] Add local tables for harness runs, events, artifacts, and approvals.
    - [x] Keep Maya as one identity; the harness manages work only.
- [x] **15.2. Deeper Harness Migration**
    - [x] Add explicit harness states: planning, executing, observing, verifying, waiting approval, waiting user, completed, failed, and cancelled.
    - [x] Classify browser, screen, document, project, skill, self-heal, app, scheduled, and Omi-prep work into named subgraph paths.
    - [x] Keep LangGraph checkpoints as the resume source while `harness_runs` remains the inspectable index.
    - [x] Keep old routers as harness tool providers during migration.
- [x] **15.3. Workflow Coverage V1**
    - [x] Route new browser, screen, document, project, skill, self-heal, app, and scheduled workflows through the harness where recognized.
    - [x] Keep existing command routers as compatibility wrappers.
    - [x] Let scheduled tasks use the harness when `ENABLE_LANGGRAPH_HARNESS=1`.
- [x] **15.4. Approval and Safety**
    - [x] Pause harness runs for sensitive actions.
    - [x] Resolve plain yes, no, cancel, and later locally.
    - [x] Preserve existing hard blocks for private exposure.
- [x] **15.5. Resume and Artifact Tracking**
    - [x] Add resume summaries for what Maya is working on, where she stopped, what is pending, continue, and close workflow.
    - [x] Ask which workflow to continue when multiple workflows are active.
    - [x] Add structured artifact tracking with kind, path or URL, source tool, existence, delivery status, and checksum.
    - [x] Support artifact inspection for latest files and last file.
- [x] **15.6. Screen and Browser Grounding**
    - [x] Add a shared grounded observation model for browser DOM, visible text, screen status, app state, confidence, and provenance.
    - [x] Persist grounded observations for screen and browser workflows.
    - [x] Keep browser sensitive-click approval owned by the browser workflow so old guided-click behavior still works.
- [x] **15.7. Skill Learning Loop**
    - [x] Store skill metadata: triggers, non-triggers, tools, provider lane, safety boundary, tests, review notes, usage, failures, and disable reason.
    - [x] Require approval plus trigger, non-trigger, safety, happy-path, failure-path, and regression tests before a proposed skill becomes active.
    - [x] Add natural commands for testing and improving skills.
    - [x] Keep proposed, approved-but-untested, draft, and disabled skills out of active prompt context.
    - [x] Add `skill_outcome_events` so Maya can record skill outcomes, failures, corrections, missing steps, and workflow references.
    - [x] Add per-skill memory for what worked, what failed, preferences, examples, tests, safe data notes, and blocked data notes.
    - [x] Add the private skill library layout under `maya_skills/active`, `proposed`, `disabled`, `research_notes`, and `tests`.
    - [x] Add weekly no-key skill review summaries for usage, failures, stale skills, proposals, disabled skills, and new candidates.
    - [x] Add safe user-model storage with source, confidence, allowed categories, and hard sensitive-data blocks.
    - [x] Add channel adapter contracts so Telegram, iMac voice, Omi, and future true channels translate input/output without owning personality, skills, safety, or routing. Mudra Link v1 is not a channel; it only emits hotkeys.
    - [x] Add honest self-improvement language checks so Maya cannot claim learning, proposal updates, or active skill improvement without inspectable evidence.
- [x] **15.8. Self-Heal Loop**
    - [x] Add self-heal stage logging for detected, isolated, proposed, closed, and future repair states.
    - [x] Add self-heal inspection answers for what broke, tests, patch direction, restart safety, and repair reports.
    - [x] Keep patching, deploy, restart, delete, and broad refactor approval-gated.
    - [x] Add scoped memory self-heal dry-run/proceed/abort commands with durable snapshots under `backups/self_heal_memory/`.
    - [x] Reject `/selfheal force` for the memory-only heal.
    - [x] Require rollback behavior, explicit retrieval pass criteria, and a post-heal core/profile target of 80 percent usage or less.
- [x] **15.9. Hardware Preparation**
    - [x] Keep direct Mudra event recording disabled; Mudra Link v1 uses app-level hotkey mapping instead.
    - [x] Prepare Omi transcript metadata for future pendant ingestion.
    - [x] Keep Omi Pendant behavior disabled until hardware testing; Mudra Link behavior is handled by the vendor app, not Maya runtime.
- [x] **15.10. Harness Tests**
    - [x] Add harness store, graph, resume, browser, screen, disabled-Mudra-seam, and Omi smoke tests.
    - [x] Add harness artifact, grounding, detailed resume, skill learning loop, and self-heal loop smoke tests.
    - [x] Include new harness hardening tests in `may1_rehearsal.py`.
    - [x] Keep every `.py` file under 300 lines.
- [x] **15.11. Native Checkpoint Resume**
    - [x] Make LangGraph checkpoint snapshots the workflow source of truth.
    - [x] Keep `harness_runs` as an inspectable index/dashboard instead of authoritative state.
    - [x] Give every user workflow a unique `harness:<run_id>` thread id.
    - [x] Keep background workflows on `harness:background:<task_id>`.
    - [x] Add checkpoint-native resume, approval, decline, cancellation, and snapshot paths.
    - [x] Add a one-time migration helper for old active `state_json` rows.
- [x] **15.12. Replay Safety**
    - [x] Add `harness_action_ledger` for deterministic idempotency keys.
    - [x] Route harness tool execution through a single ledger gateway.
    - [x] Dedupe event, approval, artifact, and structured artifact writes.
    - [x] Prevent replay from duplicating file writes, skill scaffolds, self-heal reports, and background delivery.
    - [x] Pause uncertain browser/app/send/payment-style actions instead of blindly replaying them.
- [x] **15.13. Native Checkpoint Tests**
    - [x] Add native checkpoint resume smoke.
    - [x] Add idempotency replay smoke.
    - [x] Add approval checkpoint smoke.
    - [x] Add multi-workflow checkpoint resume smoke.
    - [x] Add document, skill, self-heal, and background replay smokes.
    - [x] Run checkpoint and idempotency cases three times inside their smoke tests.
    - [x] Add the new checkpoint/replay smokes to `may1_rehearsal.py`.

## 🧭 Phase 16: Everyday Use and Desktop Maya Workspace
*Goal: Make Maya's everyday output visible on the Desktop and make daily work easier to inspect.*

- [x] **16.1. Desktop Maya Workspace**
    - [x] Add a shared workspace helper with `~/Desktop/Maya` as the default root.
    - [x] Create standard folders for documents, notes, presentations, spreadsheets, drawings, projects, artifacts, screenshots, reports, and inbox.
    - [x] Keep legacy `~/Downloads/Kampung AI` readable for older generated artifacts.
    - [x] Keep source code separate from user-facing output.
- [x] **16.2. Excel and Office Output**
    - [x] Add Excel `.xlsx` draft creation.
    - [x] Route Excel files to `~/Desktop/Maya/spreadsheets`.
    - [x] Open Excel drafts on the iMac when requested from iMac.
    - [x] Send Excel drafts through Telegram when requested from Telegram.
    - [x] Open latest Word, PowerPoint, Excel, and Markdown files from Desktop Maya by type or name.
    - [x] Open `.docx` in Word, `.pptx` in PowerPoint, `.xlsx` in Excel, and `.md` in Cursor by default with TextEdit fallback.
    - [x] Treat iMac highlighted selection as an anchor and read wider active Excel, Word, PowerPoint, Markdown, and browser DOM context when safe.
    - [x] Block sensitive spreadsheet content.
- [x] **16.3. Workflow Desk**
    - [x] Add a conversational workflow desk summary.
    - [x] Show active workflows, active project, and latest artifacts.
    - [x] Add background workflow listing.
    - [x] Add latest artifact opening.
    - [x] Allow matching workflow cancellation through natural language.
- [x] **16.4. Everyday Layer**
    - [x] Add daily cockpit answers for what today looks like.
    - [x] Add focus recommendations from tasks and blockers.
    - [x] Add waiting-on tracker using the task table.
    - [x] Add approval inbox aggregation.
    - [x] Add project cockpit.
    - [x] Add quiet mode preference.
- [x] **16.5. Tests**
    - [x] Add Desktop workspace and Excel smoke coverage.
    - [x] Add waiting-on smoke coverage.
    - [x] Add daily cockpit smoke coverage.
    - [x] Add workflow desk smoke coverage.

## 🧩 Phase 17: Extensibility And Audit Layer

- [x] **17.1. Security Manifests**
    - [x] Add a manifest schema for skills and MCP tools.
    - [x] Track read, write, delete, send, browse, click, form, account, external API, memory, and artifact permissions.
    - [x] Track approval requirements and hard blocked actions.
    - [x] Add manifest inspection and smoke coverage.

- [x] **17.2. MCP Registry**
    - [x] Add MCP server registry storage.
    - [x] Track command, environment needs, enabled state, permission scope, owner, and usage.
    - [x] Add proposal, approval, enable, disable, and audit flows.
    - [x] Add MCP registry smoke coverage.

- [x] **17.3. Skill Import Standard**
    - [x] Import local skill folders through `SKILL.md`.
    - [x] Import external skill repositories through `npx skills add owner/repo`.
    - [x] Run external skill installs in a temporary folder.
    - [x] Store imported skills as proposed only.
    - [x] Infer triggers, tools, permissions, and manifest from the imported skill.
    - [x] Require review and activation tests before use.

- [x] **17.4. Starter Skill Catalog**
    - [x] Add starter skills for flights, shopping, browser research, document critique, slide critique, network troubleshooting, finance tracking, habit planning, app control, and Excel tracker creation.
    - [x] Keep starter catalog skills proposed until approved and tested.
    - [x] Add catalog smoke coverage.

- [x] **17.5. Skill Performance Analyzer**
    - [x] Analyze repeated success, repeated failure, corrections, and blocked outcomes.
    - [x] Create improvement proposals without changing active behavior.
    - [x] Add performance analyzer smoke coverage.

- [x] **17.6. Maya Desk**
    - [x] Create a private local audit report under `~/Desktop/Maya/reports/maya-desk.html`.
    - [x] Include workflows, approvals, artifacts, skills, user model, MCP usage, skill outcomes, and cost.
    - [x] Add Maya desk smoke coverage.
    - [x] Keep all `.py` files under 300 lines.

## Phase 18: Local Wake Word Training
*Goal: Make Maya wake locally through headphones without wasting provider tokens.*

- [x] **18.1. Archived Voice Wake Experiments**
    - [x] Archive local sample recorder for positive and negative clips.
    - [x] Archive local scorer prototype using embeddings.
    - [x] Archive one-stage and two-stage probes.
    - [x] Keep iMac live voice activation disabled permanently unless Zainal explicitly reopens it.

- [x] **18.2. Archived Official Training Pipeline**
    - [x] Install official training dependencies locally.
    - [x] Add official training asset preparation under `~/Desktop/Maya/artifacts/wakeword_official`.
    - [x] Add Python 3.14 compatibility wrapper for openWakeWord training.
    - [x] Generate synthetic samples with Piper.
    - [x] Run feature augmentation and ONNX export.

- [x] **18.3. Closed Direction**
    - [x] Record that v1 official model was experimental only.
    - [x] Record that v2 was experimental only.
    - [x] Record that v3 was experimental only.
    - [x] Archive scorer tuning outside the live path.
    - [x] Close the probe direction because manual realtime streaming is the selected path.
    - [x] Keep soak result as historical note only.

## Phase 19: Artifact Quality Skills, Unified Documents, And Canonical Memory
*Goal: Stop treating Telegram, iMac, documents, skills, and memory as separate surfaces. Maya should create the same quality artifacts everywhere and remember one canonical truth per saved fact.*

### Source Of Truth Rule

- [x] **19.0. Single Checklist Source**
    - [x] Use this file, `KAMPUNG_AI_CHECKLIST.md`, as the only roadmap/checklist for this phase.
    - [x] Do not create or maintain a separate roadmap checklist for artifact quality, skills, or memory architecture.
    - [x] Keep skill files, tests, and helper modules as runtime artifacts only; progress and next-step ownership stay here.
    - [x] Update `KAMPUNG_AI.md` when architecture changes, because the checklist tracks execution while `KAMPUNG_AI.md` explains how Maya works.
    - [x] Future `what is next?` answers must inspect the first incomplete item in this phase instead of repeating old Telegram regression tests.
    - [x] Treat the old Telegram feature regression set as passed unless a new regression appears or this checklist asks for a specific retest.

### Quality Skills Creation

- [x] **19.1. Artifact Quality Skills**
    - [x] Add active `word_artifact_quality` skill.
    - [x] Add active `excel_artifact_quality` skill.
    - [x] Add active `powerpoint_artifact_quality` skill.
    - [x] Add active `html_app_artifact_quality` skill.
    - [x] Add test checklist files for all four artifact quality skills under `maya_skills/tests`.
    - [x] Register the four skills in Maya's skill registry so `show active skills` and skill context can expose them.
    - [x] Keep these skills as quality standards and review context, not magic executable tools.
    - [x] Wire runtime code to explicitly load the skill context when reviewing artifacts.

- [x] **19.2. Skill Acceptance Rules**
    - [x] Each quality skill defines trigger examples.
    - [x] Each quality skill defines non-trigger examples.
    - [x] Each quality skill defines safety and hard-no boundaries.
    - [x] Each quality skill defines local validation expectations.
    - [x] Each quality skill defines Claude review expectations.
    - [x] Each quality skill defines provider ownership: Gemini for role drafts, Artisan for HTML/code implementation after the Codex lane is wired, Claude for review, local libraries for actual files.
    - [x] Add `artifact_quality_smoke.py` to prove the skill files pass Maya's scaffold evaluator and local QA works.
    - [x] Record complete-by-default artifact behavior: creation should use the strongest relevant quality standards immediately, while `edit` or `/edit` is reserved for follow-up changes.

### Artifact Quality And Review Standards

- [x] **19.3. Shared Artifact QA Contract**
    - [x] Add `ArtifactQualityResult` with artifact type, path, pass/fail state, summary, issues, warnings, draft model, review model, validation steps, repair flag, and delivery readiness.
    - [x] Add structured QA issue metadata: rule id, severity (`blocker`, `warning`, `info`), rule class (`mechanical`, `open_world`, `semantic`), message, and evidence.
    - [x] Add local HTML validation for doctype, structure, inline CSS/JS, interactive controls, code-fence leakage, and common corrupted CSS/HTML markers.
    - [x] Add local Word validation for `.docx` openability, headings, content density, placeholder text, malformed markdown leakage, and generated summary.
    - [x] Add local Excel validation for `.xlsx` openability, populated cells, table-like rows, frozen panes, and formulas when formulas are implied.
    - [x] Add Claude artifact review helper that loads the relevant artifact quality skill and records Claude usage when a live key is present.
    - [x] Fail open with a warning when Claude is unavailable, while still enforcing local validation.
    - [x] Add QA disagreement governance: open-world/semantic validator disagreements can use targeted Gemini arbitration, mechanical blockers remain validator-authoritative, and `/review` shows weekly disagreement activity with resolved items crossed out.

- [x] **19.4. Word Quality Gate**
    - [x] Keep Gemini role-based drafting as the Word content source.
    - [x] Build real `.docx` files with local document tooling.
    - [x] Run local Word QA before final delivery.
    - [x] Run Claude Word review when available.
    - [x] Save a useful artifact summary with the structured artifact record.
    - [x] If QA fails, say it is a draft with issues instead of calling it final.

- [x] **19.5. Excel Quality Gate**
    - [x] Keep local workbook creation for trackers, budgets, comparisons, and cost sheets.
    - [x] Run local Excel QA before final delivery.
    - [x] Run Claude Excel review when available.
    - [x] Apply QA to general Excel drafts, budget trackers, testing comparisons, cost trackers, and travel-budget workbooks.
    - [x] If QA fails, say it is a draft with issues instead of calling it final.
    - [x] Make Excel workbook styling use pastel colors by default.
    - [x] Upgrade food-trip budget workbooks so they include per-food or per-restaurant budget rows, estimated cost, actual cost, variance, totals, restaurant/source links in notes where available, and useful suggestions.

- [x] **19.6. PowerPoint Quality Gate**
    - [x] Preserve existing high-quality PowerPoint path: Gemini role content, Claude presentation review, local PPTX build, render QA, and topic-safe polish pass.
    - [x] Add `powerpoint_artifact_quality` as the explicit quality skill standard.
    - [x] Add `powerpoint_design_taste` as an active Maya skill adapted from Leonxlnx `design-taste-frontend`.
    - [x] Keep Design Engineering as taste context for presentation polish.
    - [x] Feed the PowerPoint skill text directly into every presentation polish/review prompt, not only the generic skill registry.
    - [x] Add PowerPoint theme selection: dark/editorial by default, pastel only when Zainal explicitly asks for pastel/light/bright/white or says he does not want dark.
    - [x] Set Nano Banana 2 / Gemini 3.1 Flash Image as the default PowerPoint visual generator policy, with Nano Banana Pro for high-value final decks.
    - [x] Keep Grok out of normal PowerPoint image generation so Grok remains reserved for live voice, Pulse, current/news, and only explicit Grok requests.
    - [x] Add Gemini image generation/sourcing for PowerPoint decks when images improve comprehension.

- [x] **19.7. Office Output Quality Sprint**
    - [x] Define what "good output" means for Word, Excel, and PowerPoint beyond route/tool success.
    - [x] Add a bounded Gemini artifact preflight role agent for Word, Excel, and PowerPoint so short requests produce a scenario-specific blueprint before drafting/building.
    - [x] Upgrade Word output so first drafts have stronger structure, useful detail, summaries, and fewer generic sections.
        - [x] Define Word good output as scenario fit, section depth, actionability, specificity, local openability, and Claude review, not just route success.
        - [x] Add scenario-specific Word structures for travel itineraries, research briefs, technical guides, proposals, checklists, meeting notes, letters, reports, plans, and explainers.
        - [x] Feed the selected Word scenario structure into Gemini before drafting.
        - [x] Canonicalize or reject generic headings such as Role And Assumptions, Working Context, and Key Decisions when the scenario does not call for them.
        - [x] Make local Word QA inspect scenario headings and content depth, not only `.docx` openability.
        - [x] Accept short natural Word requests such as `Seoul food trip doc`, `router setup guide in Word`, and `proposal doc for Kampung AI`.
        - [x] Add a layered natural artifact parser so phrases like `Can you make me a food trip document to Seoul for two days?` route without one-off regex patches.
        - [x] Add voice transcript repair for split artifact requests such as `It needs to be in document` so Maya creates and attaches the file instead of promising future work.
        - [x] Add focused 500-case post-STT artifact replay covering Word, Excel, PowerPoint, split clauses, filler words, wakephrase glitches, and filename-noise rejection.
        - [x] Add broad 10,000-case Telegram post-STT replay covering artifact creation, latest-document edits, natural slashless commands, paid-voice long-work parking, normal-chat negatives, filler words, cutoffs, disturbances, wakephrase glitches, and filename-noise rejection.
        - [x] Ask one short clarification question when essential artifact parameters are missing instead of creating generic files.
        - [x] Resolve travel document destinations from explicit wording or clear recent context, ask when missing, and reject destination mismatches during Word QA.
        - [x] Default short city food-trip documents to a compact 2-day plan and reject internal duration mismatches.
        - [x] Strengthen router/WiFi technical guides with required admin password, SSID, WiFi password, WPA2/WPA3, firmware, and verification content.
        - [x] Repair proposal drafts before delivery when they contain empty Out of Scope labels, incomplete tiered frameworks, or raw markdown dividers.
        - [x] Replace one-pass Word repair with bounded internal Word QA retries before Maya delivers or reports a hard failure.
        - [x] Set default artifact QA retry cap to 3 attempts for Word/Excel and PowerPoint visual QA, while keeping environment overrides available and clamped.
        - [x] Add bounded internal Excel rebuild retries for travel-budget and generic spreadsheet creation before Maya delivers or reports a hard failure.
        - [x] Add a Word quality smoke test that builds real `.docx` files and validates multiple everyday scenarios.
        - [x] Add Word golden artifact smoke tests that inspect real `.docx` content for travel, router, and proposal scenarios.
        - [x] Add natural latest-document Word edit support so short follow-ups such as `update that to 4 days` update in place, while explicit copy/new-version requests create a new visible version.
        - [x] Fix natural Word edit parsing so `the document` does not get partially matched as `doc`, corrupting titles such as `Ument`.
        - [x] Add shared artifact session state for Telegram and iMac so follow-up edits use artifact type, path, topic, structured state, revision count, status, and expiry instead of only a latest-file string.
        - [x] Set active artifact session lifetime to 24 hours, with successful new artifact creation making that channel's artifact active.
        - [x] Apply edit deltas such as duration, people count, and destination changes to the active artifact state before rebuilding or editing the file.
        - [x] QA edited artifacts against the new intended state, not the stale original title or previous topic.
        - [x] Add Telegram and iMac artifact-session continuity smoke coverage for create-then-edit flows.
        - [x] Enforce short two-to-three-word artifact filenames and keep parameters/noisy voice fragments in metadata/content instead of filenames.
        - [x] Remove obsolete parser-only edit smoke coverage that could pass while the real artifact continuity path failed.
        - [x] Route creation-verb itinerary, guide, proposal, report, config, checklist, and travel-plan requests to Word when no explicit artifact type is present, while keeping bare `document` ambiguous.
        - [x] Track rejected local drafts separately so `give me the rough` or `send me the draft` attaches the rough file instead of falling through to normal chat.
        - [x] Add PuTTY/router CLI Word QA so terminal edit requests require actual sample config commands, placeholder explanation, verification commands, and save/rollback guidance.
    - [x] Upgrade Excel output so workbooks feel immediately useful, visually polished, and domain-specific by default.
        - [x] Replace weak generic sheet names such as `Maya Draft` with meaningful sheet names.
        - [x] Add stronger generic workbook styling: pastel title/header/section fills, neutral editable body cells, frozen panes, real Excel tables, sensible widths, wrapped text, and number formats.
        - [x] Add estimated, actual, variance, and total formulas to generic budget trackers.
        - [x] Strengthen comparison/tracker workbook structures so they are not generic notes tables.
        - [x] Strengthen local Excel QA to reject weak sheet names, budget/tracker workbooks missing estimated/actual/variance fields, and food-trip workbooks missing restaurant/source/suggestion detail.
        - [x] Add `excel_golden_artifact_smoke.py` to inspect actual workbook content for generic budget and Seoul food-trip scenarios.
    - [x] Upgrade PowerPoint output so decks have stronger narrative, visual design, image use where useful, and less draft-level polish.
        - [x] Replace generic Markdown-to-slide conversion with scenario-specific deck spines for travel/food, technical, proposal, and general decks.
        - [x] Remove generic title-slide fallback copy such as `Draft prepared from grounded Maya notes`.
        - [x] Store PowerPoint QA/review results so `/review` can explain the latest deck pass/fail state.
        - [x] Keep visual asset support through the Gemini PPTX image path when enabled and when the topic benefits from visuals.
        - [x] Treat remaining `draft-level` PowerPoint polish as a failed quality gate instead of a clean deliverable pass.
        - [x] Move PowerPoint explanatory detail into speaker notes and keep visible slide text short and visual.
        - [x] Enable Google/Gemini image generation by default for visual PowerPoint topics.
        - [x] Require generated or safely sourced visual assets before visual-topic decks are called deliverable.
        - [x] Insert multiple Gemini/Google visual assets for visual-topic decks instead of limiting decks to one cover image.
        - [x] Set the PowerPoint visual-asset hard cap to `ceil(slide_count * 1.3)` and require visual-topic decks to cover every slide with images by default.
        - [x] Use image-led PowerPoint layouts for visual topics so photos do not sit on top of text.
        - [x] Insert PowerPoint visuals with aspect-preserving crop/cover and fail QA for raw stretched images.
        - [x] Feed PowerPoint design taste into Gemini preflight/drafting and Claude review through active skill context.
        - [x] Render PowerPoint previews internally for QA, but do not send JPEG/contact-sheet previews in Telegram unless explicitly requested.
        - [x] Insert Gemini/Google visual assets after text/layout repair so generated images are not lost by later rebuilds.
        - [x] Do not attach rejected editable `.pptx` drafts or JPEG previews in Telegram by default.
        - [x] Store internet-derived PowerPoint visual-design guidance in Maya's active PowerPoint artifact skill.
        - [x] Retry PowerPoint visual QA and Claude polish internally up to a safety cap instead of sending every failed attempt to Telegram.
        - [x] Add deterministic PowerPoint rescue spines for repeated draft-level polish failures before Maya gives up.
    - [x] Add golden artifact tests for one Word, one Excel, and one PowerPoint example that inspect actual file content, not only route labels.
    - [x] Run one real Telegram Office quality pass only after the generators are improved.
        - [x] Word Telegram pass: `seoul-food-trip-v3.docx` attached, route used Gemini artifact preflight + Word QA + Claude Opus review, review passed.
        - [x] Excel Telegram pass: `seoul-budget-tracker-v6.xlsx` attached, route used Gemini artifact preflight + local Excel QA + Claude Opus review, review passed.
        - [x] PowerPoint Telegram delivery retest: `seoul-food-trip-deck-v14.pptx` attached successfully after the timeout fix.
        - [x] Add longer Telegram media/document upload timeouts and visible fallback path messaging when file upload fails.
        - [x] Verified latest local PowerPoint has 6 slides, speaker notes on every slide, QA pass, and no stretched images.
        - [x] Fix latest-document PowerPoint summaries so they inspect the delivered `.pptx` and ignore stale intermediate draft-level polish rows.
        - [x] Add local Word visual QA before Maya calls Word output polished.

- [x] **19.7a. HTML App Quality Gate**
    - [x] Route future serious HTML/app-building to The Artisan with Codex.
    - [x] Record that standalone HTML document creation is a lightweight artifact workflow, while app-building belongs to Artisan projects.
    - [x] Keep the current standalone HTML document path gated as a lightweight document workflow only until the Artisan app lane is implemented.
    - [x] Feed `html_app_artifact_quality` into Claude HTML review.
    - [x] Run local HTML QA after review.
    - [x] Save and attach a real `.html` file instead of pasting source into Telegram.
    - [x] Recognize typo-style HTML creation requests already covered by the document parser.
    - [x] Add browser render smoke for generated HTML files when the browser runtime is available.
    - [x] Move app-building acceptance out of the current manual Telegram document regression; focus current testing on memory and document creation first.
    - [x] Gate app-building implementation until Word, Excel, and PowerPoint output quality is good enough.
    - [x] Add a project-based app-building lane where The Artisan creates code inside an active project folder with `src`, `assets`, tests, and browser/local QA expectations.
    - [x] Route real app-building through Gemini build brief plus Artisan implementation; use `/complex` first when the scope is non-trivial.
    - [x] Require app-building tests to prove Artisan did the primary build; Gemini fallback may be useful for tiny throwaway HTML drafts but does not count as app-building success.
    - [x] Live-test project app building with Codex after login is confirmed.

### Unified Document Creation Across iMac And Telegram

- [x] **19.8. Canonical Document Router**
    - [x] Keep `DocumentActionRouter` as the canonical path for Markdown, HTML, Word, Excel, and PowerPoint creation.
    - [x] Keep Telegram text document requests on `DocumentActionRouter`.
    - [x] Keep Telegram voice document requests flowing through xAI STT, then `DocumentActionRouter`.
    - [x] Keep iMac document requests on `DocumentActionRouter` through the normal command route.
    - [x] Route the older iMac presentation shortcut into `DocumentActionRouter` instead of its old local-only PPTX shortcut.
    - [x] Keep network troubleshooting as a special local diagnostic workflow, but run Word artifact QA on its generated `.docx`.
    - [x] Move remaining special document-producing workflows into a shared builder interface instead of letting each workflow hand-roll final delivery.

- [x] **19.9. Channel-Specific Delivery Only**
    - [x] iMac delivery opens or focuses the native app when appropriate.
    - [x] Telegram delivery attaches generated files.
    - [x] Latest-document path is recorded for created artifacts.
    - [x] Structured artifacts are recorded for direct document actions.
    - [x] Telegram last-document replies should keep important paths visible as text instead of only voice.
    - [x] Add a regression that asks for the last document by voice and verifies Telegram includes path text plus a useful summary.

### Canonical Memory IDs

- [x] **19.10. Canonical Memory Store**
    - [x] Add `canonical_memory_items` with `memory_id`, `kind`, `subject_key`, `content`, `value`, `scope`, `source_channel`, `source_ref`, `confidence`, `status`, `created_at`, `updated_at`, `last_used_at`, `expires_at`, `pinned`, `temporary`, and `test_marker`.
    - [x] Add a deterministic canonical memory ID from kind, subject key, and scope.
    - [x] Add a unique truth index over kind, subject key, and scope.
    - [x] Add temporary/test-memory detection for regression, smoke, and Telegram test facts.
    - [x] Add canonical backfill from existing preferences and lessons for weekly memory.

- [x] **19.11. Canonical Save, Recall, And Forget**
    - [x] Explicit `remember` and preference learning writes canonical memory first-class records.
    - [x] Pending confirmed learning writes canonical memory records.
    - [x] Direct memory questions search canonical memory before preferences, lessons, curated memory, or session search.
    - [x] Forgotten canonical subjects block fallback recall from old duplicated stores.
    - [x] `/forget` marks matching canonical memory as forgotten and still removes derived preferences, lessons, summaries, history, session search rows, curated memory, and fuzzy traces.
    - [x] Add `canonical_memory_smoke.py` for save, recall, forget, and no-leak regression.
    - [x] Add a real migration command that reports dedupe counts and links old rows to canonical IDs instead of only backfilling active facts.

### Memory Activation Rules

- [x] **19.12. First Activation Layer**
    - [x] Inject relevant canonical memories into prompt context as `Saved facts`.
    - [x] Keep pinned canonical memories eligible for stronger activation.
    - [x] Keep temporary test memories from activating unless query-relevant.
    - [x] Keep expired or forgotten canonical memory out of recall.
    - [x] Keep direct memory answers honest: if canonical memory has no active answer, Maya says she does not have it saved.
    - [x] Add scoring decay based on age and reinforcement count.
    - [x] Add explicit pin/unpin commands for canonical memories.
    - [x] Add a direct inspector that shows canonical memory IDs and activation class.

### Weekly Memory Distillation

- [x] **19.13. Canonical Weekly Input**
    - [x] Weekly memory dry run backfills canonical memories before summarizing.
    - [x] Weekly memory samples active non-temporary canonical memories.
    - [x] Weekly memory excludes temporary and test-marker memories by default.
    - [x] Weekly summary reports canonical memory counts and canonical fact signals.
    - [x] Make live weekly provider distillation write new stable memories through canonical memory only.
    - [x] Record canonical memory IDs used in each weekly summary.
    - [x] Add Claude weekly memory review for overreach, false assumptions, unsafe memory, and confirmation-needed facts.
    - [x] Add `weekly_memory_runs` audit rows for manual, Telegram, and launchd weekly memory executions.
    - [x] Make the launchd weekly memory job pass `--trigger-source launchd` so autonomous runs can be distinguished from manual runs.
    - [x] Add `/weekly status` to show latest summary and recent weekly-memory run audit rows.
    - [x] Add `/weekly run` to start a saved weekly-memory pass from Telegram.
    - [x] Load `.env` for weekly provider agents so launchd can see Gemini and Claude keys.
    - [x] Add a local weekly-memory durability guard that rejects transient global project facts, generated-artifact observations, trip-plan details, test facts, and sensitive data even if a provider approves them.
    - [x] Add weekly-memory reviewer fallback so Claude review failures save a conservative summary, save zero unreviewed canonical facts, and audit the reviewer error instead of failing the whole launchd run.
    - [x] Backfill the failed Sunday June 7, 2026 launchd weekly-memory run for `2026-W23` after adding the reviewer fallback.
    - [x] Run weekly memory manually with live providers and verify audit rows record provider calls, saved facts, rejected facts, and canonical memory IDs.
    - [x] Add a user-facing `/weekly` formatter that hides raw paths, JSON blobs, provider debug text, and canonical IDs while keeping `/weekly status` as the audit view.
    - [x] Verify one unattended launchd weekly memory run after the next scheduled Sunday 20:00 trigger.

### Project And Task Retention

- [x] **19.14. 90-Day Retention Layer**
    - [x] Add project activity registry with `last_activity_at`, `retention_state`, `deletion_pending_at`, and tombstones.
    - [x] Add task retention columns and use task `updated_at` as the activity signal.
    - [x] Mark projects/tasks `deletion_pending` after 90 days without qualifying activity.
    - [x] Keep a 7-day warning window before hard deletion.
    - [x] Hard-delete Maya project/task/workflow/harness/search records only; never delete local project folders or files.
    - [x] Renew project/task activity when Zainal opens, talks about, edits, or writes memory/progress for it.
    - [x] Keep passive retrieval, listing, cleanup scans, and weekly distillation from renewing activity.
    - [x] Run retention cleanup from `/memorycleanup` and weekly memory before distillation.
    - [x] Show pending retention warnings in status/workflow desk.
    - [x] Add regression coverage for 89-day active, 90-day pending, 7-day deletion, touch renewal, file preservation, task/workflow cleanup, and weekly-memory exclusion.

### Regression Tests

- [x] **19.15. Local Smoke Coverage**
    - [x] Add artifact quality smoke test.
    - [x] Add canonical memory smoke test.
    - [x] Add both new smokes to `may1_rehearsal.py`.
    - [x] Update existing document smoke expectations for the new QA route labels.
    - [x] Run document, artifact quality, canonical memory, memory control, learning, weekly memory, Telegram routing, and iMac workflow smokes together.

- [x] **19.16. Manual Telegram Regression**
    - [x] Telegram text Word: created `2-day-seoul-food-trip-v1.docx`; verified attachment, clean filename, route, cost, local Word QA, and Claude Opus review.
    - [x] Telegram text Excel: created `seoul-budget-tracker-v2.xlsx`; verified attachment, clean filename, route, cost, traveler-count fix, local Excel QA, and Claude Opus review. Deeper food-trip quality upgrade remains tracked separately under 19.5.
    - [x] Telegram text PowerPoint: created `2-day-seoul-food-trip-v1.pptx`; verified attachment, clean filename, route, cost, Visual QA pass, and Claude Opus review.
    - [x] Defer HTML/app-building manual regression into the project-based `/complex` app-building lane.
    - [x] Telegram voice: created `two-days-seoul-food-trip-v1.docx` by voice; verified xAI STT, route, cost, attachment, visible filename text, local Word QA, and Claude Opus review.
    - [x] Memory temporary fact: saved, recalled, forgot, and confirmed no-leak recall for `my telegram memory test snack is hotteok`.
    - [x] Weekly memory: ran fresh `2026-W22` dry run after temporary tests and verified forgotten test fact `hotteok` did not become durable weekly memory.

- [ ] **19.17. Manual iMac Regression - June 8**
    - [x] iMac text/voice: create one Word, Excel, and PowerPoint artifact; verified before May 25, 2026 that iMac voice can create Word, Excel, and PowerPoint through Maya.
    - [x] Defer iMac HTML/app-building regression into the project-based `/complex` app-building lane.
    - [x] Prepare `imac_june8_regression.py` with preflight checks and exact manual prompts for June 8.
    - [x] Add smoke coverage proving the June 8 regression checklist is present and does not falsely mark manual-live proof as complete.
    - [ ] Confirm iMac live voice uses the same architecture as Telegram memory, document creation, workflow desk, and weekly memory.
    - [ ] Verify native app continuity: open last document, open specific document, summarize document, and focus the correct app.
    - [ ] Verify iMac voice long-work execution: Maya starts local browser/document work during the live voice session, keeps listening, and reports the result without internal wording.
    - [x] Disable `ENABLE_LOCAL_WAKE_SCORER` for live use.
    - [x] Keep local wake experiments separate from paid Grok and out of the live path.
    - [x] Add voice device intent policy: Sony or `Zainal’s Headphone` allows Maya wake.
    - [x] Block AirPods and iMac audio from local Maya wake.
    - [x] Replace Mudra proximity/pinch trigger ideas with Mouse Mode hotkey pass-through: Twist maps to `Option + Space`, Double Twist maps to `Option + Escape`.
    - [x] Add a no-Grok local voice integration smoke for wake acknowledgement.
    - [x] Add hotkey voice smoke for deliberate local trigger plus 5 second idle close.
    - [x] Add hotkey voice smoke for manual stop.
    - [x] Remove false-wake acceptance target because voice wake activation is removed.
    - [x] Remove wake detection acceptance target because voice wake activation is removed.
    - [x] Do not connect local wake to Maya. Mudra Link is only an external hotkey controller in v1.
    - [x] Do not use xAI STT confirmation for the current one-stage headphone path.
    - [x] Add `hardware_live_proof.py` so hardware/live readiness can be audited without pretending physical proof has happened.
    - [x] Add smoke coverage for hardware/live proof readiness and manual-live-required boundaries.
    - [x] Avoid continuous long headphone capture because it can degrade media audio quality.

## Phase 20: Kampung AI Hardening Sprint

*Goal: Strengthen Maya into an inspectable, demo-ready, agentic AI system with reproducible quality gates.*

- [x] **20.1. Sprint Documentation And Capability Memory**
    - [x] Document memory self-heal guardrails, `/selfheal dryrun`, `/selfheal proceed`, `/selfheal abort`, force rejection, rollback path, and retrieval pass criteria in `KAMPUNG_AI.md`.
    - [x] Track the scoped memory self-heal implementation in this checklist.
    - [x] Document the Hardening Sprint scope in `KAMPUNG_AI.md`.
    - [x] Add this Hardening Sprint checklist as the source of truth for the next hardening steps.
    - [x] Document Kampung AI as the Maya Personal Agent Harness, not just a Telegram bot, model router, or LangGraph workflow set.
    - [x] Record the target harness components: `MayaThreadManager`, `MayaEventStore`, `MayaToolRegistry`, `MayaPermissionKernel`, `MayaLoop`, and future internal `MayaAppServer`.
    - [x] Record that public references must come from official/public sources, not leaked Claude Code source.
    - [x] Add a compact "Maya current capabilities" section that records current percentages and capability boundaries so future sessions do not re-litigate what already exists.

- [x] **20.1A. Maya Personal Agent Harness Spine**
    - [x] Define a minimal internal SDK boundary for `start_thread`, `send_message`, `call_tool`, `request_approval`, `create_artifact`, `write_memory`, and `resume_thread`.
    - [x] Add a `MayaThreadManager` wrapper over current Telegram, iMac, project, screen, voice, weekly-memory, and background workflow state.
    - [x] Add a `MayaEventStore` append-only event spine while keeping current tables as domain/materialized views.
    - [x] Add a formal `MayaToolRegistry` with input/output schema, permission scope, side-effect level, approval requirement, cost risk, and replay-safety classification.
    - [x] Add a central `MayaPermissionKernel` before tool execution.
    - [x] Document the `MayaLoop` in README and Maya Desk traces.
    - [x] Defer local JSON-RPC/WebSocket `MayaAppServer` until the internal protocol is stable.

- [x] **20.2. Refactor Files Over 300 Lines**
    - [x] Run `code_health.py` and capture the current violation list.
    - [x] Refactor files over 300 lines only where a real module boundary exists.
    - [x] Keep behavior unchanged while extracting helpers, data models, command handlers, validators, templates, and delivery utilities.
    - [x] Add or update targeted smokes for each extracted subsystem.
    - [x] Require `code_health.py` to pass before the sprint is considered stable.
    - [x] Verification evidence: `code_health.py` passes with no over-300-line violations; `local_ci.py` passes compile, code health, and scored eval; `scored_eval_suite.py` reports 19/19; all five `run_demo.py` workflows pass; `git diff --check` passes.

- [x] **20.3. Dependency Manifest**
    - [x] Create a machine-readable dependency manifest for Python packages, system tools, macOS permissions, local apps, launchd jobs, provider keys, MCP servers, and optional hardware.
    - [x] Make the manifest distinguish required, optional, local-only, remote-only, and future hardware dependencies.
    - [x] Wire `doctor.py` or a new readiness command to read the manifest and report missing items clearly.
    - [x] Include Codex subscription-auth, Blender, ffmpeg, Office apps, Telegram token, Gemini, Claude, xAI, and weekly-memory launchd status.

- [x] **20.4. Local CI First, GitHub Actions Later**
    - [x] Create one local CI entrypoint that runs compile checks, code health, route tests, memory tests, document golden tests, Artisan smokes, Blender/Maker smokes, and Maya Desk smoke.
    - [x] Ensure local CI does not require live provider calls by default.
    - [x] Add an optional live-provider mode that is explicit and cost-aware.
    - [x] Add GitHub Actions only after local CI is stable and the workflow can run without private macOS or provider secrets.

- [x] **20.5. Scored Eval Suite**
    - [x] Expand `golden_conversation_eval.py` into a scored eval runner with pass/fail totals.
    - [x] Add categories for routing, memory save/forget, weekly memory, Word, Excel, PowerPoint, self-heal, Artisan, Blender/Maker, safety, and Maya Desk.
    - [x] Store eval output as JSON and a human-readable summary.
    - [x] Make failed evals show the exact capability and scenario that regressed.

- [x] **20.6. Five Polished Demo Workflows**
    - [x] Add one-command demo runner entrypoints such as `run_demo telegram_document`, `run_demo memory_weekly`, `run_demo self_heal`, `run_demo artisan_project`, and `run_demo blender_maker`.
    - [x] Define demo pass/fail criteria for each of the five demo workflows before polishing the demos.
    - [x] Create demo replay logs that record what Maya did, what tools/routes were used, what cost lane was recorded, and what artifacts were created.
    - [x] Demo 1: Telegram creates Word, Excel, and PowerPoint artifacts with route, review, attachment, and local-file continuity.
    - [x] Demo 2: Memory save, recall, forget, no-leak recall, and weekly distillation status.
    - [x] Demo 3: `/complex` self-heal plan, approval gate, repair report, dry run, and rollback-safe proceed path.
    - [x] Demo 4: Artisan project/app handoff with Gemini build brief, Codex subscription-auth guard, QA result, transcript, and delivery summary.
    - [x] Demo 5: Blender/Maker 3D printable output with source, `.blend`, `.stl`, dimensions, README, preview, and no physical print action.

- [x] **20.7. Public-Style Technical README**
    - [x] Write a README for a technical investor/product audience.
    - [x] Explain Maya's lanes, memory architecture, artifact quality model, `/complex`, Artisan, Blender/Maker, safety gates, workflow desk, and Maya Desk.
    - [x] Add a system architecture diagram for the README.
    - [x] Add a known limitations section that clearly says what is partial, local-only, scheduled later, or hardware-dependent.
    - [x] Add a "what Maya will not do without approval" section covering repo apply, restart, deploy, delete, upload, booking, payment, credentials, physical printing, and external sends.
    - [x] Add a small cost table showing normal, heavy, and demo usage expectations by lane.
    - [x] Include demo workflows, dependency overview, local setup shape, limitations, and what is still private or local-only.
    - [x] Avoid secrets, raw personal memory, and overclaiming unavailable capabilities.

- [x] **20.8. Maya Desk As Product Surface**
    - [x] Upgrade Maya Desk from debug report to local audit cockpit.
    - [x] Show workflow status, approvals, routes, costs, artifacts, memory health, eval score, dependency readiness, provider readiness, and recent failures.
    - [x] Add a generated report timestamp and clear pass/fail indicators.
    - [x] Add a smoke test that verifies the report contains the core sections and no raw secrets.

- [x] **20.9. Extra Hardening Requirements**
    - [x] Add route/cost audit consistency checks so route labels, models, and cost flags do not drift.
    - [x] Add capability readiness reporting so Maya can honestly say what is ready, partial, blocked, or future.
    - [x] Add backup/rollback drills for memory and repo-apply paths.
    - [x] Add privacy/redaction checks for public README, Maya Desk, demos, and any external report.
    - [x] Ensure demo replay notes are linked from README, Maya Desk, and the eval suite so the five demos can be rerun without inventing prompts.

---
*Updated June 3, 2026*

## Phase 21: Proof Packaging And Source-Aware Research

*Goal: Make the current system easy to verify, safe to show, and harder to overclaim before adding more features.*

- [x] **21.1. Lock The Current Work**
    - [x] Push the Phase 20 baseline commits to GitHub.
    - [x] Confirm `git status -sb` is clean after the push.
    - [x] Create checkpoint tag `phase-20-hardening-complete`.
    - [x] Keep this pushed baseline as the recoverable state before Phase 21 changes.

- [x] **21.2. Source-Aware Gemini Research Workflow**
    - [x] Add a source-aware Gemini research module with explicit source/research intent detection.
    - [x] Use Gemini grounded search when `GOOGLE_API_KEY` is configured.
    - [x] Format answers with source links and warn when citations are unavailable or not official.
    - [x] Block sensitive/private-info requests before provider calls.
    - [x] Route explicit research/source requests through `Gemini source-aware research`.
    - [x] Preserve routing priority: `/complex`, commands, safety/policy, Artisan, Claude review, and Grok current/news remain ahead of source research.
    - [x] Add fake-provider and assistant-route smoke coverage.

- [x] **21.3. Clean Demo Evidence**
    - [x] Keep old failed demo logs for internal history.
    - [x] Add `logs/demos/latest.json` pointing only to the latest passing demo for each workflow.
    - [x] Add `logs/demos/latest.md` with demo name, pass/fail, latest replay log path, artifacts/evidence, criteria, and command output evidence.
    - [x] Redact private local home paths from public latest demo evidence.
    - [x] Update README to point readers to `logs/demos/latest.md`.

- [x] **21.4. Strengthen README For Outside Readers**
    - [x] Add `Why Kampung AI Is Different`.
    - [x] Add `What Is Implemented Now`.
    - [x] Add `What Is Not Production Ready Yet`.
    - [x] Add `How To Verify The System Locally`.
    - [x] Add a five-demo table with commands and expected output.
    - [x] Add safety and cost-control tables.

- [x] **21.5. Make Maya Desk The Proof Surface**
    - [x] Show latest eval score.
    - [x] Link latest passing demo evidence logs.
    - [x] Show dependency readiness.
    - [x] Show provider readiness.
    - [x] Show route and cost audit.
    - [x] Show hardening audit summary and keep recent failures separate from passing proof.

- [x] **21.6. Verify Local CI Is The Truth**
    - [x] Keep `local_ci.py` as the default proof command.
    - [x] Run Python compile checks.
    - [x] Run blocking code health.
    - [x] Run scored eval suite.
    - [x] Run hardening audit smoke.
    - [x] Run latest demo evidence check.
    - [x] Keep live provider checks optional and explicit.

- [x] **21.7. Add Demo Evidence Checker**
    - [x] Validate the five latest demo logs exist.
    - [x] Validate each latest demo passed.
    - [x] Validate each demo has criteria.
    - [x] Validate command output is captured.
    - [x] Validate each demo has an artifact or evidence path.
    - [x] Validate secret-shaped values do not appear in demo proof.

- [x] **21.8. Add Public Redaction Pass**
    - [x] Check README.
    - [x] Check latest demo summary and JSON.
    - [x] Check latest eval log.
    - [x] Flag API keys, tokens, private keys, OTPs, bank/card data, personal private memory, and unnecessary local private paths in public-facing proof files.

- [x] **21.9. Re-score After Proof Packaging**
    - [x] Run `./venv/bin/python local_ci.py`.
    - [x] Confirm scored eval output is current: 100.0%, 25/25 passing.
    - [x] Confirm `hardening_audit.py` reports zero public redaction issues.
    - [x] Record expected post-packaging scores: personal agent 8.0/10, engineering maturity 7.2/10, public technical credibility 6.8/10, product/investor readiness 6.3/10.

- [x] **21.10. What Not To Add Yet**
    - [x] Do not add more AI models.
    - [x] Do not add more hardware features.
    - [x] Do not add WhatsApp yet.
    - [x] Do not add commercial onboarding yet.
    - [x] Do not add cloud deployment yet.
    - [x] Treat proof quality, not feature count, as the current bottleneck.

---
*Updated June 3, 2026*

## Phase 22: Real-World Reliability And Live Proof

*Goal: Move from deterministic proof to repeated real-world reliability without overclaiming hardware or live voice readiness.*

- [x] **22.1. Local Checkpoint**
    - [x] Commit the Maya skill creation lifecycle repair locally.
    - [x] Keep the Phase 22 branch local-only until Zainal explicitly asks for a push.
    - [x] Preserve the pushed Phase 20/21 baseline as the recoverable remote state.

- [x] **22.2. Live Evidence Tracking**
    - [x] Add `live_test_evidence.py` as the source for live/manual proof status.
    - [x] Record Telegram document, voice-note, memory, route, and file-delivery regression as passed.
    - [x] Record the June 3 Telegram Web cross-function text run: 200 planned tests, 200 PASS, 0 CHECK, 0 FAIL. Evidence: `logs/live_tests/telegram_cross_function_200_2026-06-03.md`.
    - [x] Record that the final 200-test run explicitly covered Telegram text chat, memory, safety, Word create/edit/send/review, Excel create/edit/review, PowerPoint create/edit/send/review, `/complex`, skills, browser-safe routing, current/news/research, Malay/Manglish, delivery audit, turn audit, and route/cost/provider inspection.
    - [x] Record that the report uses delivery-log verification only for Telegram Web bubble-capture misses, not as a substitute for failed Maya delivery.
    - [x] Record pre-May-25 iMac voice Office artifact creation as passed based on Zainal's live result.
    - [x] Keep iMac long-work in-session voice execution as `manual-live-required`.
    - [x] Keep iMac native app continuity as `manual-live-required`.
    - [x] Keep Omi transcript sync as `manual-live-required`; Mudra v1 is hotkey pass-through and does not require a Maya-side gesture parser.
    - [x] Add smoke coverage for live evidence defaults and updates.

- [x] **22.3. Maya Desk Live Proof Separation**
    - [x] Show live evidence separately from latest passing demo logs.
    - [x] Show 7-day reliability soak status.
    - [x] Show browser field-test scenarios.
    - [x] Keep smoke-test proof and live/manual proof visibly distinct.

- [x] **22.4. Browser Field-Test Proof**
    - [x] Add `browser_field_tests.py` with practical prompts for flights, date changes, cheaper comparisons, source-aware research, safe field fill, and booking/payment/private-data stop points.
    - [x] Add deterministic smoke coverage for browser routing and safety boundaries.
    - [x] Expand browser field scenarios to include Airbnb, Booking.com, YouTube navigation, product comparison, search-result selection, popup/page-change recovery, official-source research, payment stop, upload stop, and private travel-data refusal.
    - [x] Add explicit live-run pass criteria and safety boundaries for each browser benchmark case.
    - [ ] Run real browser sessions and record outcomes for the prepared prompts.

- [x] **22.5. 7-Day Reliability Soak**
    - [x] Add `live_reliability_soak.py` to track missed replies, wrong routes, voice timeouts, memory mistakes, file delivery failures, browser failures, cost spikes, and false saved claims.
    - [x] Add deterministic smoke coverage for clean and failing soak days.
    - [x] Run a one-day Telegram Web stress pass across chat, memory, documents, audit, safety, workflow, current/news, browser-safe, skill, and meta prompts.
    - [x] Fix and prove the June 3 weak paths found by the stress pass: early safety gate, stale browser-workflow hijack, Artisan false-positive routing, unsupported-action false positives, Word transit-tip edit, Excel notes-column edit, Excel task-tracker creation, and PowerPoint topic/title QA.
    - [ ] Complete seven normal-use daily live soak records.
    - [ ] Review any soak failures and convert repeated failures into repair tasks.

- [ ] **22.6. Hardware And Live Voice Proof**
    - [ ] Validate Omi real transcript sync.
    - [ ] Validate Omi privacy filtering and ambient memory behavior.
    - [x] Validate the chosen Mudra v1 design: Mouse Mode remains active and gestures are mapped in the Mudra Link app to existing Maya hotkeys.
    - [x] Live-test Twist and Double Twist against Maya's running hotkey channel.
    - [ ] Validate iMac live long-work voice execution with in-session browser/document work, interruption, status recall, and later state resume.

- [x] **22.7. 9-Path Proof Tooling**
    - [x] Add `reliability_scorecard.py` for a 30-day reliability scorecard.
    - [x] Extend `live_reliability_soak.py` to store 30 days and track success totals, uptime minutes, estimated cost, workflow recoveries, and user corrections.
    - [x] Add `browser_benchmark.py` to score deterministic browser route/safety readiness separately from live browser outcomes.
    - [x] Add Maya Desk trace metrics, failure-like trace metrics, browser benchmark status, and 30-day reliability status.
    - [x] Add smoke coverage for the reliability scorecard and browser benchmark.
    - [ ] Complete 30 normal-use daily records before claiming 9/10 daily reliability.
    - [ ] Record live browser benchmark outcomes before claiming browser-agent maturity.

- [x] **22.8. Grok Voice Transcript Replay Proof**
    - [x] Add `voice_transcript_policy.py` for deterministic long-work classification and transcript noise notes.
    - [x] Add `voice_command_aliases.py` so spoken iMac commands like `show route`, `show status`, `weekly status`, `self heal dry run`, `this is complex...`, `remember...`, `forget...`, and `create skill...` can route without slash syntax.
    - [x] Add voice transcript cleanup for filler words, self-correction, background-noise markers, repeated starts, and dangling cut-off endings before voice intent routing.
    - [x] Preserve the rule that xAI voice does not personally execute long document, browser, skill, coding, memory, or project work; it starts Maya's local tools through a clean voice facade.
    - [x] Add explicit travel price capture for spoken or typed flight, Airbnb, Booking.com, hotel, accommodation, and stay prices so budget workbooks can preserve those values.
    - [x] Wire visible browser travel selections into budget memory: choosing a Google Flights, Booking.com, or Airbnb priced option saves the selected provider/option/price into `maya_travel_plan`, and the one-sheet travel budget workbook consumes those values. Verified by `browser_task_step_smoke.py`.
    - [x] Fix country-level travel Word QA so "Kazakhstan itinerary" can include in-country cities such as Almaty and Astana without being rejected as destination mismatches. Verified against the live-generated `kazakhstan-itinerary-v3.docx`, `document_species_smoke.py`, `word_quality_smoke.py`, and live Telegram turn 5743.
    - [x] Add `grok_voice_transcript_replay_500.py` and `grok_voice_replay_fakes.py` for isolated deterministic replay without live provider spend.
    - [x] Run the 500-case replay. Result: 500 PASS, 0 FAIL. Evidence: `logs/live_tests/grok_voice_transcript_replay_500_2026-06-04.md`.
    - [x] Confirm the replay covered the then-current voice-to-worker routing, memory, documents, `/complex`, safety gates, Grok-not-long-work policy, final response shape, live skills, skill creation/suggestion/approval, healing commands, travel budget price capture, slashless spoken commands, and noisy/cut-off transcripts.
    - [x] Keep real iMac in-session voice work validation under 22.6; deterministic transcript replay is not physical microphone/websocket proof.

- [x] **22.9. Phase 22 Readiness 700 Proof**
    - [x] Add `phase22_readiness_700.py` as the consolidated software-readiness benchmark for June 8 preparation.
    - [x] Cover document quality: Word render/visual QA, Excel formulas/format/domain/usefulness checks, PowerPoint render/notes/dark-theme/aspect-ratio checks, and failed-quality boundaries.
    - [x] Cover browser/agent workflow: YouTube, flight search, Booking.com/Airbnb comparison, product/research prompts, safe form filling, source-aware routing, and stop-before-login/payment/upload/submit behavior.
    - [x] Cover `/complex`: plan, approval, checkpoint, rollback, trace, repair/report, and final-report expectations.
    - [x] Cover memory over time: canonical canaries, aged recall, forget/no-leak behavior, simulated 30-day scorecard, and saturation-safe proof boundaries.
    - [x] Cover Blender/Maker software path: deterministic maker templates, Blender export QA, mesh/dimension proof, no ready-to-print overclaim, and physical-print approval boundaries.
    - [x] Cover voice readiness simulation: session open/close, work started/completed, voice resume state, duration guard, and no long work executed directly by xAI voice.
    - [x] Cover multitasking simulation: Maya can keep short conversation state separate while a worker continues document/background work and appends relevant context.
    - [x] Run the 700-case readiness benchmark. Result: 700 PASS, 0 FAIL. Evidence: `logs/live_tests/phase22_readiness_700_2026-06-04.md`.
    - [x] Keep physical proof separate: this does not claim real iMac microphone/websocket/speaker, paid billing, Bambu print execution, Omi, Mudra, or real elapsed 30-day reliability.

- [x] **22.10. Maya Voice Transcript Replay 700 Proof**
    - [x] Add `maya_voice_transcript_replay_700.py` to send 700 noisy voice-style transcripts through `KampungAssistant.handle_text(..., input_type="voice")`.
    - [x] Ensure long-work transcripts route into Maya's local work path instead of being answered as ordinary voice chat.
    - [x] Cover document creation, memory save/recall/forget, spoken routing commands, `/complex`, safety gates, skill request/approval, browser-safe routing, travel price capture, and daily conversation.
    - [x] Keep replay state isolated in a temporary DB and temporary skill/workspace folders so test memories and skill scaffolds do not pollute Maya's real memory.
    - [x] Run the 700-case Maya voice transcript replay. Result: 700 PASS, 0 FAIL. Evidence: `logs/live_tests/maya_voice_transcript_replay_700_2026-06-04.md`.
    - [x] Keep physical proof separate: this does not claim real microphone, xAI websocket, Ara speaker output, live paid billing, Telegram upload, Bambu print execution, Omi, or Mudra.

- [ ] **22.11. Phase 22 Closeout**
    - [x] Update `KAMPUNG_AI.md` with Phase 22 reliability architecture.
    - [x] Update `README.md` with live proof boundaries and Maya Desk proof separation.
    - [x] Update this checklist as the Phase 22 source of truth.
    - [x] Align Phase 22 progress language so the current operational estimate is 82 to 84 percent, not an overclaimed 88 percent.
    - [x] Improve Maya Desk with proof-boundary snapshot, operational score estimate, and pending physical/live proof sections.
    - [x] Strengthen the June 8 iMac live-test checklist with voice, Telegram/browser, Office, memory, `/complex`, in-session voice work, and evidence-capture prompts.
    - [x] Prepare browser benchmark evidence requirements with deterministic route/safety proof and live-run scoring placeholders.
    - [x] Run `/selfheal dryrun` equivalent locally. Result: no memory/files/cache/services changed; current core/profile 42%/82%; projected 42%/37%; latest document preserved.
    - [x] Run targeted Phase 22 smokes.
    - [x] Rerun `phase22_readiness_700.py`. Result: 700 PASS, 0 FAIL.
    - [x] Rerun `maya_voice_transcript_replay_700.py`. Result: 700 PASS, 0 FAIL.
    - [x] Rerun `grok_voice_transcript_replay_500.py`. Result: 500 PASS, 0 FAIL.
    - [x] Run `local_ci.py`.
    - [x] Run redaction check on the June 3 Telegram Web 200-test report.
    - [x] Keep live-only work separate: iMac realtime voice, live browser field sessions, Omi/Mudra, physical print, seven-day soak, and 30-day reliability remain pending until actual evidence exists.
    - [x] Zainal explicitly approved pushing this Phase 22 state on June 4, 2026.
    - [x] Verify GitHub reports `zainal-rr/kampung-ai-maya` as `PRIVATE` before pushing.
    - [x] Push the verified Phase 22 closeout commit to the private GitHub remote.

- [x] **22.12. Architecture Hygiene And Documentation Separation**
    - [x] Remove the retired alternate coding-provider architecture and legacy deep-routing path from active code.
    - [x] Delete obsolete implementation/test entry points that represented the retired architecture.
    - [x] Rename shared lane prompt helpers to `lane_prompts.py`.
    - [x] Add `legacy_architecture_removed_smoke.py` and wire it into `local_ci.py`.
    - [x] Verify active files do not contain retired architecture markers except inside the guard test itself.
    - [x] Preserve the previous full `KAMPUNG_AI.md` content as `docs/maya_operating_doctrine.md`.
    - [x] Replace `KAMPUNG_AI.md` with a concise architecture source.
    - [x] Add root-level `KAMPUNG_AI_FULL.md` as the long-form architecture and operating doctrine.
    - [x] Add `docs/public_architecture.md` for public/investor-safe explanation.
    - [x] Add `docs/proof_and_readiness.md` for scores, proof boundaries, and remaining validation.
    - [x] Update `README.md` with the architecture document map.

## Phase 23: Reliability Sprint - Memory Time Audit And Self-Heal Execution

*Goal: Strengthen the two highest-leverage non-live areas: memory over time and real checkpointed agentic self-heal execution. Browser field reliability is deferred to live/browser testing.*

- [x] **23.1. Memory Time Audit**
    - [x] Add append-only `memory_audit_events`.
    - [x] Audit canonical writes as `canonical_write`.
    - [x] Audit same-subject canonical updates as `canonical_update`.
    - [x] Audit forget operations as `canonical_forget`.
    - [x] Audit direct recall as `canonical_recall`.
    - [x] Audit relevant prompt activation as `activation`.
    - [x] Audit weekly provider candidates as `weekly_candidate`.
    - [x] Audit weekly accepted facts as `weekly_save`.
    - [x] Audit weekly rejected facts as `weekly_reject`.
    - [x] Store redacted previews and content hashes instead of full sensitive content.
    - [x] Surface recent audit rows in `/memory inspect`.
    - [x] Surface recent audit rows in Maya Desk.

- [x] **23.2. Memory Canaries And Leak Detection**
    - [x] Add `memory_canaries`.
    - [x] Seed deterministic active, forgotten, temporary-expired, project-active, and pinned canaries.
    - [x] Add canary checks for forgotten leakage through active canonical memory.
    - [x] Add canary checks for derived leaks through preferences, lessons, raw history, session search, compacted summaries, weekly summaries, and curated memory.
    - [x] Verify temporary canaries do not become durable profile memory.
    - [x] Add `leak_check` audit events.
    - [x] Surface canary status in `/memory inspect`.
    - [x] Surface canary status in Maya Desk.

- [x] **23.3. Weekly Memory Anti-Drift Guard**
    - [x] Prevent live weekly distillation from recreating canonical subjects already marked forgotten, expired, or superseded.
    - [x] Audit weekly reviewer failure/rejection paths.
    - [x] Keep canonical memory as the truth layer; audit remains evidence only.

- [x] **23.4. Checkpointed Agentic Self-Heal**
    - [x] Convert approved `/complex self-heal` from proposal-only into a durable checkpointed harness execution path.
    - [x] Record `diagnose`, `snapshot`, `plan_patch`, `await_approval`, `apply_patch_isolated`, `verify`, `repair_once`, `final_report`, and `failed` states.
    - [x] Require a snapshot before mutation.
    - [x] Write memory rollback snapshots before memory-only self-heal actions.
    - [x] Pause for second approval before isolated mutation.
    - [x] Keep repo apply-back, restart, deploy, delete, broad cleanup, and destructive actions under separate explicit approval.
    - [x] Let resume continue the same checkpointed run.
    - [x] Let decline cancel cleanly.
    - [x] Create repair reports when verification fails.

- [x] **23.5. Automated Proof**
    - [x] Add `memory_time_audit_smoke.py`.
    - [x] Add `self_heal_execution_smoke.py`.
    - [x] Update `complex_agentic_workflow_smoke.py` for checkpointed self-heal behavior.
    - [x] Add new smokes to `local_ci.py`.
    - [x] Run focused memory audit/canary smokes.
    - [x] Run focused self-heal execution smokes.
    - [x] Run full `local_ci.py` after this sprint's documentation and code changes. Result: 34 PASS, 0 blocking failures.

- [x] **23.6. Memory Retrieval Upgrade**
    - [x] Add `memory_recall_eval.py` with exact, paraphrase, Malay/Manglish, voice-noisy, temporal-old, forgotten, absent, and forget over/under-deletion cases.
    - [x] Record recall eval reports under `logs/evals/` with hard floors for exact recall, forgotten leaks, false direct recalls, and forget safety.
    - [x] Add `canonical_memory_fts.py` and wire SQLite FTS5/BM25 hybrid retrieval into canonical memory activation.
    - [x] Use the `unicode61` tokenizer with no Porter stemming so Malay/Manglish recall is not degraded by English-only stemming.
    - [x] Add env-gated structured memory extraction through `memory_extraction.py`, off by default and enabled only with `MEMORY_EXTRACTION_LIVE=1` plus `GOOGLE_API_KEY`.
    - [x] Keep deterministic extraction as the no-key fallback and require provider output to pass schema, kind, scope, token-overlap, durability, and sensitivity validation.
    - [x] Echo provider-shaped saves as `saved as subject -> value` so bad extraction is visible at write time.
    - [x] Add `memory_watchdog.py` to seed/check canaries, detect audit silence after recent recalls, report stale curated rows, and exit nonzero on alerts.
    - [x] Add `forget_registry.py` so every forgettable memory/index store has one registered cleanup path.
    - [x] Preserve the existing `/forget` output format while moving execution into the registry.
    - [x] Add `docs/memory_upgrade_plan.md` with baseline metrics, pin-ranking follow-up metrics, run commands, and embedding decision gates.
    - [x] Measure the post-FTS5 baseline: exact recall@3 1.00, paraphrase recall@3 0.40, Malay/Manglish recall@3 0.71, forgotten leaks 0, absent false direct recalls 0.
    - [x] Fix pinned-memory ranking so pinned facts guarantee inclusion without outranking unrelated lexical evidence.
    - [x] Measure the pin-ranking fix: exact recall@1 1.00, Malay/Manglish recall@1 0.57, voice-noisy recall@1 0.83, temporal-old recall@1 1.00.
    - [x] Keep embeddings out of the default path for now, but mark the embedding rerank gate as fired because paraphrase recall@3 remains 0.40.

## Phase 24: Hardening Review, Document Species, Domain Knowledge, And Agentic Loop

Full detail: `SESSION_CHANGE_REPORT.md`. Validation plan: `KAMPUNG_AI_VALIDATION_TEST_CHECKLIST.md`.

- [x] **24.1. Security And Correctness Review Fixes**
    - [x] Add closed-by-default Telegram sender allowlist (`TELEGRAM_ALLOWED_CHAT_IDS`) across all four handlers, with rejected senders logged.
    - [x] Fix the dead context-command bug in `assistant.py` (result was unconditionally overwritten with None).
    - [x] Stop harness start-marker hijacking of normal chat ("what type of pasta") with message-start `START_COMMAND_RE`.
    - [x] Remove the canonical memory 80-row recall cliff and add a status index.
    - [x] Block forgotten-memory resurrection by derived writers (`allow_resurrect=False` for weekly and Omi) with `canonical_write_blocked_forgotten` audit events; preserve pinned status on re-save.
    - [x] Feed the permission kernel human-readable arg text, Luhn-validate card detection, and tighten bare token/secret markers.
    - [x] `load_dotenv(override=False)`, fail-loud missing `GOOGLE_API_KEY`, init-once memory DB setup, `requirements.txt`.
    - [x] Remove the live batch validator word-count false-pass (`local.passed` required).
    - [x] Remove hardcoded `/Users/...` paths (`voice.py`, `sieve.py`, `demo_evidence.py`) and restore the Python 3.10 floor (`document_style.py`).
- [x] **24.2. Document Species And Deck Visual Identity**
    - [x] Word: workshop_plan, sop, investor_brief, strategy species; exact Day 1..N coverage and validation for 2-12 day itineraries.
    - [x] Excel: `excel_species.py` schema archetypes (content calendar, operations/research/habit logs, inventory with formulas, CRM, project plan, schedule, dev tracker, financial model with gap and coverage-ratio formulas); money lanes guarded.
    - [x] PPTX: teaching/review/pitch/issue arcs with distinct closings; shared `deck_species.py`; species accent palettes, layout rhythm offsets, and species-tinted backgrounds within dark/pastel families (`office_pptx_palette.py`); contrast bounds enforced.
    - [x] Visual-asset trigger word-boundary fix plus plain/internal veto; legacy PPTX smokes repaired against current production behavior.
    - [x] `document_species_smoke.py` with real prompt shapes, including saved-file color assertions.
- [x] **24.3. Domain Knowledge Packs (Deterministic Retrieval)**
    - [x] `domain_knowledge.py`: skill-file-driven routing (strong/weak triggers, phrase vetoes), lexical chunk scoring, whole-recipe retrieval under `recipes/`, token budget, silence-over-noise gate, mtime caching.
    - [x] Wire into `skill_registry.build_prompt_context` with `domain:<skill_id>` usage logging; proposed packs stay inert until promoted.
    - [x] Finance pack: `maya_skills/proposed/finance_credit_analysis.md` plus `docs/finance/` (3 concepts, 5 worked recipes with formulas and worked examples).
    - [x] Verify the networking pack (`docs/networking/`) parses, routes, and passes the skill scaffold validator.
    - [x] `skill_domain_smoke.py` including the real banking-case prompt.
- [x] **24.4. Agentic Loop (Opt-In, Level 4 Scaffolding)**
    - [x] verify→plan loop edge with `MAX_STEPS=8` budget; default single-pass behavior unchanged when `MAYA_AGENTIC_LOOP=0`.
    - [x] `harness_llm_planner.py` (plan, choose_next_action, verify_goal) wired to the GPT lane with cost tracking (`gpt_harness_planner_calls`).
    - [x] Executor consumes planner tool choices through the permission kernel: deny → honest refusal, sensitive → approval pause, `memory.write` inline, browser/screen/document remapped to workflow executors, unknown tools fall back safely.
    - [x] Per-step domain knowledge retrieval with `domain_knowledge` trace events.
    - [x] `harness_agentic_deep_smoke.py`: happy path, approval pause, permission deny — all deterministic.
- [x] **24.5. Skill Hygiene**
    - [x] Word-boundary matching for built-in skill keywords; checkout-guard and telegram-send collision keywords tuned ("loan book"/"Preference Share" no longer inject guard/send skills).
    - [x] Move `maya_skills/active/fake.md` to `disabled/`; reject the miscaptured "Can you update that to 4 days" skill proposal.
- [x] **24.6. Telegram Conversation Contract**
    - [x] Greeting-only Telegram turns now answer warmly instead of returning the old empty-input fallback.
    - [x] Expired pending artifact requests and expired active artifact sessions are cleaned before Telegram routing.
    - [x] Short meta-followups such as "what do you mean" use only the immediate previous assistant reply instead of stale artifact context.
    - [x] Normal model chat is blocked from claiming files, attachments, browser work, or memory writes without verified tool/delivery evidence.
    - [x] Strong document/artifact requests that hit command-router failure return an honest document failure instead of falling through to normal chat.
    - [x] `telegram_conversation_contract_smoke.py` pins the June 10 regressions.
- [x] **24.7. Context Window Design Doctrine**
    - [x] Add `docs/context_window_design_2026-06-12.md` as the agreed source of truth for Maya working memory.
    - [x] State clearly that the context window is design-approved, stages 0-2 are built, and the master switch remains off by default.
    - [x] Lock the five-layer separation: raw window, rolling summary, session search, canonical memory, and domain packs.
    - [x] Record the rule that session continuity is not durable belief.
    - [x] Require one future `assemble_context()` chokepoint instead of scattered prompt appends.
    - [x] Require facts-only taint metadata and kernel-derived policy, not stored policy decisions.
    - [x] Require forget watermark handling across raw window, rolling summary, session search, and context display.
    - [x] Require rolling summaries to rebuild from raw turns, never summary-of-summary.
    - [x] Require source pointers for rolling-summary claims.
    - [x] Require salience gating by taint before any future canonical-memory candidate flow.
    - [x] Require retrieval strengthening to be rank-only, bounded, and decaying.
- [ ] **24.8. Context Window Implementation**
    - [x] Stage 0: add C0-C7 canaries from `docs/context_window_design_2026-06-12.md` and keep them green before any live enablement.
    - [x] Stage 1: add turn store, facts-only taint metadata, `assemble_recent_context()`, token-budgeted raw window, per-turn cap, and forget watermark. Keep `MAYA_CONTEXT_WINDOW=0` by default.
    - [x] Stage 2: add rolling compaction, rebuild-on-forget, gist pointers, and taint inheritance.
    - [ ] Stage 3: add `/context` view from the audit manifest: loaded turns, token usage, rolling summary, excluded counts, watermarked turns, and tainted turns.
    - [ ] Stage 4: tune route-specific budgets using Phase 7 field data and `/cost`.
    - [x] Validate remember → recall → forget → ask with `MAYA_CONTEXT_WINDOW=1` and confirm no leak in the canary smoke.
    - [x] Validate tainted browser content five turns back still confirm-gates external sends until it ages out in the canary smoke.
- [ ] **24.9. iMac Validation (owner)**
    - [ ] Commit the working tree FIRST (two sessions of uncommitted work; no rollback point exists until this is done).
    - [ ] Run `KAMPUNG_AI_VALIDATION_TEST_CHECKLIST.md` end to end on the iMac with live keys.
    - [x] Live Telegram allowlist Phase 2 check: a second phone/account sent `/start`, `Hi`, and `Hello` at 2026-06-10 23:15 MYT; Maya stayed silent and `logs/launchd.stderr.log` recorded three `Rejected unauthorized Telegram chat ...` warnings.
    - [x] Smoke/proof app-control boundary: `local_ci.py` now forces `MAYA_TEST_MODE=1` for child checks, and `OSBridge` treats `_smoke.py`, `test_*.py`, `local_ci.py`, and `scored_eval_suite.py` as no-op app-control entrypoints so Word, Excel, PowerPoint, Cursor, Chrome, and notifications cannot wake during log/security/memory proof runs.
    - [x] Live Telegram Kazakhstan QA governance check: turn 5743 delivered `kazakhstan-itinerary-v3.docx` cleanly with Day 1 through Day 9 headings, `/review` turn 5744 showed Claude PASS, and `qa_disagreement_events` stayed empty for the known-good case.
    - [x] Add D10 tool-seam fix for iMac voice: raw transcripts no longer start supervised work; xAI owns semantic intent and calls `start_maya_work` / `run_browser_skill` only when ready; local Python only guards empty/unsafe/mechanically impossible tool arguments. iMac soft-QA draft delivery for Word/Excel/PPTX remains in place.
    - [ ] Live D10 retest on iMac voice: incomplete fragments do not start local work; corrected requests such as router config -> Meraki firewall config result in one xAI tool call with the full intended request; Maya must not repeat canned platform/config option lists; soft QA drafts still open.
    - [ ] Promote `network_engineering` and `finance_credit_analysis` to `maya_skills/active/` after Phase 5 checks.
    - [ ] Decide on the concurrent-session changes (cost-lane refactor, browser extension lane) and commit the working tree.
    - [ ] One week of field use; collect the disappointment list to drive the next phase.
    - [ ] Decide the wedge question before Phase 25 ends: open-source the governed spine, productize the SEA document agent, or keep Maya personal. This decision gates restructure, installer, and multi-user work.

## W4: Package Boundary Restructure

Goal: replace the flat root with package boundaries while preserving daily
operator commands through real CLI wrappers. Do not use `git stash` during W4;
dirty work must be committed as a checkpoint or explicitly discarded before
Step 0.

- [ ] **W4.0. Clean Checkpoint And Baselines**
    - [ ] Start from the clean Phase 7 checkpoint on branch `w4/restructure`.
    - [ ] Save baseline `local_ci.py` output under `logs/w4/baseline_ci.txt`.
    - [ ] Generate `logs/w4/cli_wrapper_candidates.txt` from actual `__main__` files and documented `python X.py` references.
    - [ ] Generate `logs/w4/grandfather_baseline.txt` from current package-aware code-health violations; do not hand-code this list.
    - [ ] Confirm package-aware `code_health.py` excludes `tests/` and fixture scripts, reports grandfathered debt, and fails only new violations.
- [ ] **W4.1. Package Move Waves**
    - [ ] Wave 1: move smoke/replay/eval scripts into `tests/` and update `local_ci.py` paths.
    - [ ] Wave 2: move non-smoke leaves with temporary identity shims.
    - [ ] Wave 3: move clustered modules package-by-package.
    - [ ] Wave 4: move hubs in small supervised batches.
    - [ ] Wave 5: rewrite imports, remove identity shims, and convert allowlisted root commands into real CLI wrappers.
    - [ ] Wave 6: verify `kampung_ai_app` import and app-entry dynamic paths.
- [ ] **W4.2. Wrapper Proof**
    - [ ] Root wrappers execute package entrypoints with `runpy.run_module(..., run_name="__main__")` or `main()`, not plain `sys.modules` shims.
    - [ ] `./venv/bin/python browser_extension_bridge.py --status` still works from the repo root.
    - [ ] `./venv/bin/python local_ci.py`, `doctor.py`, `service_install.py`, `run_demo.py`, `weekly_memory.py`, and live reliability run wrappers still execute safe proof modes.
- [ ] **W4.3. Independent Reviews**
    - [ ] CLI wrapper reviewer: file/line evidence plus command results.
    - [ ] Import/de-shim reviewer: no stale bare imports or compatibility shim markers.
    - [ ] Code-health/root reviewer: package-aware health, grandfather baseline, root count, ratchet.
    - [ ] Docs/checklist reviewer: runbooks and checklist match moved paths and preserved commands.
    - [ ] Browser/operational reviewer: browser bridge status, app entrypoints, service-install wrapper behavior.
- [ ] **W4.4. Final Acceptance**
    - [ ] `./venv/bin/python local_ci.py` matches the W4 baseline pass set.
    - [ ] `./venv/bin/python code_health.py` passes with package-aware scanning.
    - [ ] No `W4 compatibility shim` markers remain outside intentional command wrappers.
    - [ ] Root contains only approved wrappers/entrypoints.
    - [ ] Final worktree is clean and committed.

## Phase 25: Engine Sprint - Trust The Model With More Of The Loop

Goal: close the "strong governance, weak loop" inversion. The permission kernel,
approval gates, event traces, and budget already exist; this phase upgrades the
reasoning that drives them. Gated on Phase 24.6 validation being green.

- [ ] **25.1. Native Function Calling For The Planner**
    - [ ] Replace JSON-in-prompt action selection with native tool calling on the GPT lane (the responses API already supports tools).
    - [ ] Generate the tool schema list directly from `MayaToolRegistry` (`tool_schemas_for_llm` already exists; wire it to the provider format).
    - [ ] Keep the JSON-parsing path as the provider-agnostic fallback so deterministic smokes stay fake-able.
- [ ] **25.2. Honest Verification**
    - [ ] Replace `verify_goal` default-YES-on-error with one retry, then a reflect pass (ask the model what is missing), then finish with an explicit "unverified" marker in the trace.
    - [ ] Record verifier failures as trace events instead of only logging them.
- [ ] **25.3. Richer Observation Feedback**
    - [ ] Raise the per-observation truncation and add a compaction summary once observations exceed the prompt budget, so long runs keep early context.
    - [ ] Feed tool outputs (not just final responses) into the observation stream.
- [ ] **25.4. Every Registry Tool Reachable**
    - [ ] Extend `_AGENTIC_TOOL_WORKFLOWS` and inline handlers until every `MayaToolRegistry` tool is executable by the planner: routers become tools, not the other way around.
    - [ ] Keep the permission kernel in front of every call (deny → honest refusal, confirm → approval pause) — no bypass paths.
- [ ] **25.5. Sandbox Rides Along (Not After)**
    - [ ] Extend the Artisan isolated-worktree pattern to shell and file-writing tool execution inside the loop; host-mutating actions run in the isolated copy with apply-back approval.
    - [ ] Do not raise autonomy on unsandboxed host execution.
- [ ] **25.6. Budget Raise Last**
    - [ ] Raise `MAX_STEPS` beyond 8 only after 25.2 verification is trustworthy in live runs, with per-run cost visibility in `/cost`.
- [ ] **25.7. Integration Policy (MCP Decision)**
    - [ ] Adopt CLI-first + markdown skills as the integration pattern (matches 2026 industry direction: CLI for execution, skills for procedure, MCP only for hosted multi-tool platforms with central auth needs).
    - [ ] Keep `mcp.call` as the opportunistic escape hatch (Blender MCP stays); do not build first-class MCP plumbing without a concrete integration that has no good CLI.
- [ ] **25.8. Exit Criteria**
    - [ ] Deterministic smokes for retry/reflect verification and full tool reachability.
    - [ ] One live multi-step run per lane (research, document, memory) completing with verified status and visible cost.
    - [ ] Semantic classifier with keyword fallback scoped as the follow-on phase candidate, alongside the wedge decision outcome.

---
*Updated June 10, 2026*
