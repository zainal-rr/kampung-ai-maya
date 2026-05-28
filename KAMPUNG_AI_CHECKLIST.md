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
    - [x] **Anthropic:** The Steward review lane (Claude Sonnet 4.6).
    - [x] **Google:** The Sight default and premium lanes (Gemini 3.1 Flash and Gemini 3.5 Flash).
    - [x] **Moonshot:** The Artisan (Kimi k2.6). [Secured in .env]
    - [x] **xAI:** The Pulse (Grok 3).
    - [x] **xAI:** Ara voice notes, STT, and pulse/news lane.
    - [ ] **xAI:** Live iMac Grok Voice Agent websocket path.
    - [x] Move the remaining live-key day to May 20, 2026.
- [x] **1.3. Conductor Setup (`main.py`)**
    - [x] Write the asynchronous entry point.
    - [x] Initialize SQLite database.
    - [x] Implement the **"Friendship Guard" (Output Masking)**.
- [ ] **1.4. Channel Model Lock**
    - [ ] Define the iMac as the **primary** interaction channel.
    - [ ] Keep Telegram as a **secondary remote** channel.
    - [ ] Avoid building a visible iMac UI unless needed for maintenance/debugging.
    - [ ] Use Terminal as the short-term development host only.
    - [ ] Plan a dedicated Kampung AI app/service identity for the long term.
    - [x] Add a `launchd` background-service path for the spare iMac.
    - [x] Lock the calm default posture: routines on, Mudra/Omi adapters off until hardware day.
    - [x] Keep the iMac voice loop off during pre-key testing so Telegram is the main live quality surface.
    - [x] Add activation rules for Telegram work-location commands, external camera only, temporary hotkey voice, and future Mudra proximity.
    - [x] Add a travel testing plan where Telegram is the main away surface and Splashtop is remote maintenance only.

## 🧠 Phase 2: The Shared Brain
*Goal: Wire the model lanes so every provider does its own job correctly.*

- [ ] **2.1. The Primary Voice Presence (Grok Voice Agent + Ara)**
    - [ ] Make Grok the default live iMac conversation model.
    - [ ] Make Ara the default Maya voice identity on the iMac.
    - [ ] Keep the iMac path optimized for fluid spoken interaction.
    - [x] Lock the voice agent budget rule: manual trigger starts it, 5 seconds of silence closes it, and it is never open all day.
    - [x] Remove live voice wake activation from the roadmap. Mudra replaces wake later, hotkey is temporary.
    - [x] Add a bounded Grok Voice Agent session manager with stub transport for pre-key testing.
    - [x] Track Grok Voice Agent route and active seconds for `/route` and `/cost`.
    - [x] Prepare the real xAI websocket adapter behind disabled `real` mode.
    - [x] Add speech audio input for the real Grok Voice Agent path after manual trigger.
    - [x] Replace diagnostic file-capture voice with realtime microphone streaming for the hotkey path.
    - [x] Stream audio chunks to Grok Voice Agent instead of recording a local PCM file first.
    - [x] Use server-side turn detection for live Grok voice conversation.
    - [x] Stream Ara audio back as it arrives instead of waiting for full WAV playback.
    - [ ] Treat the current `ffmpeg` capture path as diagnostic only, not the natural iMac voice path.
    - [x] Prevent the real iMac voice-agent path from falling back to separate TTS after wake.
    - [x] Add iMac voice policy so short Malay/Manglish can stay on Grok while longer or style-sensitive Malay/Manglish routes to Gemini plus Ara.
    - [x] Add natural Ara thinking fillers for slower Malay/Manglish quality turns.
    - [x] Record the long-work handoff rule: acknowledge by voice, idle or close paid speech-to-speech while background work runs, then reopen voice for follow-up or final delivery.
    - [ ] Live-test the real xAI websocket adapter after the xAI key arrives.
- [ ] **2.2. The Mind (GPT-5.5)**
    - [x] Implement "Escalation Logic" for high-complexity strategy.
    - [x] Lock GPT usage to explicit complex cues only.
    - [x] Add GPT Plan Mode for explicit complex planning without execution.
    - [x] Add Claude pre-implementation review for GPT plans.
    - [x] Add a post-implementation Claude review hook for approved implementation workflows.
- [ ] **2.3. The Sight (Gemini 3.1 Flash with 3.5 Flash premium escalation)**
    - [x] Use Gemini 3.1 Flash as the primary Telegram text/research model.
    - [x] Use Gemini 3.5 Flash as the premium Sight lane and remove the old Pro branch.
    - [ ] Use Gemini for Omi summarization and memory distillation.
    - [ ] Add a source-aware Gemini research workflow after API keys arrive.
    - [x] Use Gemini 3.1 Flash for normal camera snapshots and escalate to Gemini 3.5 Flash only when premium sight can plausibly help.
- [ ] **2.4. The Steward (Claude Sonnet 4.6)**
    - [x] Add the Claude Steward lane for careful review requests.
    - [x] Route natural review, critique, audit, hidden-risk, and check-this-plan prompts without adding a new command.
    - [x] Add provider readiness and smoke coverage for the Anthropic key.
    - [x] Live-test the Claude Steward lane after API keys arrive.
- [x] **2.5. The Artisan (Kimi k2.6)**
    - [x] Lock Kimi as the sole provider for code generation.
    - [x] Route coding questions to Kimi as well as code generation.
    - [x] Add CLI lane safety language: safe read/test/diff work is allowed, while patching, restart, deploy, delete, upload, credential, purchase, and booking actions require approval when Maya acts autonomously.

## ⚡ Phase 3: The Neural Link (Mudra Link - Priority)
*Goal: Bridge the neural band into the interaction loop.*

- [ ] **3.1. Mudra Gesture Dictionary**
    - [ ] Map **Pinch** (Push-to-Talk).
    - [ ] Map **Flick Up** (Wake/Ambient Voice).
    - [x] Keep all gesture mappings disabled until the Mudra Link arrives.
    - [x] Record raw Mudra events without triggering actions.
    - [x] Prepare Mudra proximity activation when worn within one metre of the iMac.
- [ ] **3.2. Local BLE Fallback**
    - [ ] Direct BLE commands for system volume/sleep when offline.
- [x] **3.3. Mudra Adapter Seam**
    - [x] Add a clean event-file adapter for future Mudra integration.
    - [x] Keep the adapter disabled by default until hardware arrives.
- [ ] **3.4. Mudra Hardware Window**
    - [ ] Order Mudra Link around May 20, 2026.
    - [ ] Expect arrival and live integration window around June 3 to June 10, 2026.
    - [ ] Keep Mudra adapter in staging mode until the real band is present.

## 🎙️ Phase 4: Ambient Memory (Omi Pendant - Priority)
*Goal: Sync 24/7 capture into Maya's memory.*

- [ ] **4.1. Tailscale Ingress**
    - [ ] Configure auto-sync for Omi transcripts via Tailscale.
- [ ] **4.2. The Context Sieve**
    - [ ] Implement filter node to strip silence/noise from ambient feeds.
    - [ ] Store distilled Omi memories in the shared memory system.
    - [ ] Let Gemini own Omi transcript summarization and memory extraction.
- [x] **4.3. Omi Adapter Seam**
    - [x] Normalize `.txt` and `.json` transcript files through a dedicated adapter.
    - [x] Keep the Omi watcher optional until the hardware flow matters.
- [ ] **4.4. Omi Hardware Window**
    - [ ] Order Omi band around May 20, 2026.
    - [ ] Expect arrival and live integration window around June 3 to June 10, 2026.
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
- [ ] **5.3. Ara Voice Delivery**
    - [x] Shared audio rendering path for local playback and Telegram audio delivery.
    - [x] Scheduled briefings now speak aloud on the iMac.
    - [x] Lock Telegram replies to Ara voice notes once the xAI key is present.
    - [x] Send Telegram voice-note replies with `send_voice` when ffmpeg can convert Ara audio to Opus.
    - [x] Keep Telegram text-only before the xAI key rather than sending the wrong local fallback voice.
- [ ] **5.4. Local iMac Voice Loop**
    - [ ] Capture microphone speech on the iMac.
    - [x] Resolve local speech inputs by device name instead of fixed changing macOS indexes.
    - [x] Prefer `Zainal’s Headphone` as the named speech input and keep `iMac Microphone` as fallback.
    - [x] Disable voice wake activation for live use so idle listening is not needed.
    - [x] Remove Whisper from the live wake path because voice wake activation is scrapped.
    - [x] Keep Whisper only as an inactive fallback for one-shot transcription and offline debugging.
    - [x] Archive openWakeWord work as an experiment, not a future live trigger.
    - [x] Do not test openWakeWord for live voice activation unless Zainal explicitly reopens it later.
    - [ ] Record Zainal-specific positive wake samples and negative background samples.
    - [x] Archive old sample recorder experiment outside the live path.
    - [x] Archive old local scorer prototype outside the live path.
    - [ ] Improve the scorer beyond the first 85 percent leave-one-out baseline before live use.
    - [x] Add a two-stage wake probe: local candidate score first, tiny STT confirmation second.
    - [ ] Confirm the two-stage wake path before connecting it to live Maya.
    - [x] Skip openWakeWord live hardening because voice wake activation is scrapped.
    - [x] Do not connect openWakeWord to Maya live path.
    - [x] Keep the iMac voice channel disabled while the wake detector is being redesigned.
    - [x] Add hotkey voice channel so `Option + Space` starts Maya without always-on mic capture.
    - [x] Add `Option + Escape` manual stop for the hotkey voice session.
    - [x] Keep microphone capture closed until the hotkey starts a voice session.
    - [x] Prove hotkey can trigger the Grok Voice Agent path.
    - [ ] Do not continue natural voice testing on the `ffmpeg` file-capture hotkey loop.
    - [x] Rebuild hotkey voice as realtime streaming before the next serious iMac voice test.
    - [ ] Use Grok Voice Agent speech-to-speech for the long-term iMac conversation path.
    - [ ] Escalate to GPT-5.5 only when needed.
    - [ ] Speak replies locally through the iMac speakers with Ara.
    - [x] Set the wake window to 5 seconds so live voice does not stay open after silence.
    - [x] Let the iMac channel hand wake-session turns to the bounded Grok Voice Agent manager when enabled.
    - [x] Remove wake detection from live voice path. Manual trigger only.
- [x] **5.5. No Call Mode v1**
    - [x] Remove Loopback and virtual call audio routing after live test showed quality and stability issues.
    - [x] Remove call context tools from iMac realtime voice.
    - [x] Remove call listening and call-note behavior from local iMac voice.
    - [x] Keep Maya as normal iMac voice only when Zainal is on WhatsApp or FaceTime.
    - [x] Instruct Maya not to claim she can join, listen to, privately monitor, route audio into, or summarize calls.

## 👁️ Phase 6: Senses & AR
*Goal: Give Maya eyes through the approved external camera only.*

- [x] **6.1. MediaPipe Vision (`vision.py`)** - [TESTED SUCCESS]
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
    - [ ] Confirm launchd or final app runtime can read Cisco frames.
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

## 👟 Phase 7: Kinetic Anchor (DIY Shoes)
*Goal: Physical presence security and gait analysis.*

- [ ] **7.1. BLE Watchdog**
    - [ ] Monitor Shoe MAC address for auto-wake/sleep.
- [ ] **7.2. Gait Analysis**
    - [ ] Gemini-powered performance coaching from IMU logs.

## 📈 Phase 8: Evolution
- [x] **8.1. Memory Migration** - [COMPLETED 169 HIGH-VALUE CHUNKS]
- [x] **8.2. Weekly Reflection (Sunday 20:00)**
    - [x] Schedule and deliver weekly reflection through the routine runtime.
    - [x] System Health Heartbeat logic.
- [ ] **8.3. Unified Memory**
    - [ ] Merge iMac, Telegram, and Omi interactions into one shared memory model.
    - [ ] Prioritize direct interactions over ambient memory.
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
    - [ ] Let Gemini 3.1 Flash summarize weekly raw logs and remove conversational noise.
    - [ ] Let Gemini 3.5 Flash handle premium weekly synthesis when the week is dense, ambiguous, or needs stronger language quality.
    - [ ] Let Claude review weekly memory candidates for overreach, false assumptions, vague preferences, and unsafe memory.
    - [ ] Use GPT-5.5 only for high-value weekly memory shaping when the summary needs stricter judgement.
    - [ ] Promote dry-run weekly facts into local preferences, lessons, and tasks after provider review is available.
    - [x] Keep preferences separate from event memory.
    - [x] Retrieve relevant preferences, tasks, and long-term memory before replying.
    - [x] Filter operational/internal values like chat ids out of user-facing memory retrieval.
    - [x] Keep preference questions scoped to the preference layer instead of broad keyword-based archive search.
    - [x] Keep archive/project lore disabled by default for this new project.
    - [x] Clear legacy archive/state so this project starts from a fresh memory baseline.
    - [ ] Prevent personality drift from ambient transcripts alone.
- [ ] **8.4. Quantum Experiments**
    - [ ] Keep Quantum Leaf outside live routing until corrected smoke tests prove it is reliable.
    - [ ] Fix the Quantum Leaf smoke test so mixed-route expectations are actually checked.
    - [x] Add a deterministic quantum advisory layer for themes, vibes, hidden links, and "how should I think" framing.
    - [x] Keep the quantum layer out of dates, tasks, permissions, security, costs, money, delete, send, booking, and exact-rule paths.
    - [x] Make the advisory layer disableable by `ENABLE_QUANTUM_ADVISORY`.
    - [x] Block quantum advisory output from overriding `/complex`, coding-to-Artisan, current-news, vision, screen, commands, learning, safety, or permission routes.
    - [x] Add `quantum_advisory_smoke.py` and include it in launch rehearsal.
    - [ ] Test normal embeddings before any GCP tensor-network or PennyLane cloud path.

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
    - [x] Make `/complex` and explicit iMac complex cues use GPT-5.5 with `xhigh` reasoning effort.
    - [x] Add `/cost` as a direct Telegram usage estimate command.
    - [x] Add `/providers` as a direct Telegram provider-readiness checklist.
    - [x] Add `/route` as a direct Telegram routing-inspection command.
    - [x] Add `/context` as a direct Telegram compacted-context inspection command.
    - [x] Add `/selfheal` as a direct safe repair-proposal command.
    - [x] Add `/weekly` and natural weekly-reflection phrasing that reads the prepared weekly summary.
    - [x] Block normal Telegram text from falling through to any auto GPT-5.5 orchestrator path.
    - [x] Route incoming Telegram voice notes through transcription and then the normal Telegram routing path.
    - [x] Do not force English for xAI STT on Telegram voice notes.
    - [x] Force Malay or Manglish Telegram answers through Gemini before Ara speaks them.
    - [x] Keep Telegram voice as Ara voice notes instead of Grok Voice Agent sessions.
    - [x] Make Telegram Ara voice replies the locked default, with text-only fallback until the xAI key exists.
    - [ ] Live-test Telegram Ara voice-note replies against the xAI API.
- [ ] **9.2. Shared Orchestrator Across Channels**
    - [x] Reuse the same routing and memory context path for iMac and Telegram.
    - [ ] Keep channel adapters thin so the brain stays centralized.
    - [ ] Preserve one Maya identity across Grok, Gemini, GPT-5.5, and Kimi.
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
    - [x] Keep child browser skills explicit: `general_browser`, `google_images`, `flight_search`, `booking_com_hotel_search`, and `airbnb_stay_search`.
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
    - [x] Add a one-command provider smoke test for Gemini, GPT-5.5, Claude, Kimi, Grok, Ara TTS, and xAI STT.
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
    - [x] Add hardware readiness smoke for Omi, Mudra, wake phrases, wake window, and permission boundary.

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
- [ ] **14.3. Office Work**
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
    - [ ] Let Maya edit existing Word documents from structured chat instructions.
    - [ ] Let Maya edit existing PowerPoint decks from structured chat instructions.
    - [x] Add PPTX visual QA before Maya calls PowerPoint output polished.
    - [x] Render created or revised PPTX files and check for placeholder text, ellipsis overflow, truncated copy, missing readable text, and render count mismatch.
    - [x] Add one bounded PPTX auto-revision pass before delivery.
    - [x] If PPTX QA still fails, make Maya call it a draft with known issues instead of polished output.
    - [x] Add PPTX polish grade: draft-level, good, or strong.
    - [x] Detect repeated slide titles and incomplete sentence meaning in PPTX polish review.
    - [x] Let Claude provide a presentation polish grade after local QA passes.
    - [ ] Add equivalent visual QA before Maya calls Word output polished.
    - [ ] Use Word and PowerPoint as normal iMac apps when that is more natural than a separate UI.
- [x] **14.4. Workspace Creation**
    - [x] Create folders under `~/Desktop/Maya` by default.
    - [x] Create projects under `~/Desktop/Maya/Projects` by default.
    - [x] Add starter `docs`, `src`, `assets`, and `README.md` for new projects.
- [x] **14.5. Drawing and Image Output**
    - [x] Create simple local SVG drawings under `~/Desktop/Maya/drawings`.
    - [x] Send drawing files in Telegram and open them on the iMac depending on the active channel.
    - [x] Add an optional Gemini image-generation path through `GEMINI_IMAGE_MODEL` and `ENABLE_GEMINI_IMAGE_GENERATION`.
    - [x] Add `workspace_drawing_smoke.py` and include it in launch rehearsal.
- [ ] **14.6. Travel Booking Skill**
    - [x] Keep flight research as an active workflow so date or cheaper-option follow-ups update the browser search.
    - [x] Turn flight research into a guided browser flow with persistent search, compare, filter, click, and fill steps.
    - [ ] Support compare first, choose exact option second, confirm purchase last.
    - [ ] Block card, bank, passport, password, OTP, token, and API-key exposure.
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
    - [x] Add channel adapter contracts so Telegram, iMac voice, Omi, Mudra, and future channels translate input/output without owning personality, skills, safety, or routing.
    - [x] Add honest self-improvement language checks so Maya cannot claim learning, proposal updates, or active skill improvement without inspectable evidence.
- [x] **15.8. Self-Heal Loop**
    - [x] Add self-heal stage logging for detected, isolated, proposed, closed, and future repair states.
    - [x] Add self-heal inspection answers for what broke, tests, patch direction, restart safety, and repair reports.
    - [x] Keep patching, deploy, restart, delete, and broad refactor approval-gated.
- [x] **15.9. Hardware Preparation**
    - [x] Record Mudra events without mapping gestures to actions.
    - [x] Prepare Omi transcript metadata for future pendant ingestion.
    - [x] Keep Mudra Link and Omi Pendant behavior disabled until hardware testing.
- [x] **15.10. Harness Tests**
    - [x] Add harness store, graph, resume, browser, screen, Mudra, and Omi smoke tests.
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
    - [x] Each quality skill defines provider ownership: Gemini for role drafts, Kimi for HTML/code, Claude for review, local libraries for actual files.
    - [x] Add `artifact_quality_smoke.py` to prove the skill files pass Maya's scaffold evaluator and local QA works.

### Artifact Quality And Review Standards

- [x] **19.3. Shared Artifact QA Contract**
    - [x] Add `ArtifactQualityResult` with artifact type, path, pass/fail state, summary, issues, warnings, draft model, review model, validation steps, repair flag, and delivery readiness.
    - [x] Add local HTML validation for doctype, structure, inline CSS/JS, interactive controls, code-fence leakage, and common corrupted CSS/HTML markers.
    - [x] Add local Word validation for `.docx` openability, headings, content density, placeholder text, malformed markdown leakage, and generated summary.
    - [x] Add local Excel validation for `.xlsx` openability, populated cells, table-like rows, frozen panes, and formulas when formulas are implied.
    - [x] Add Claude artifact review helper that loads the relevant artifact quality skill and records Claude usage when a live key is present.
    - [x] Fail open with a warning when Claude is unavailable, while still enforcing local validation.

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

- [x] **19.6. PowerPoint Quality Gate**
    - [x] Preserve existing high-quality PowerPoint path: Gemini role content, Claude presentation review, local PPTX build, render QA, and topic-safe polish pass.
    - [x] Add `powerpoint_artifact_quality` as the explicit quality skill standard.
    - [x] Keep Design Engineering as taste context for presentation polish.
    - [x] Feed the PowerPoint skill text directly into every presentation polish/review prompt, not only the generic skill registry.

- [x] **19.7. HTML App Quality Gate**
    - [x] Keep Kimi K2.6 as the primary HTML/code builder.
    - [x] Keep Gemini Flash as fallback only after Kimi failure or timeout.
    - [x] Feed `html_app_artifact_quality` into Claude HTML review.
    - [x] Run local HTML QA after review.
    - [x] Save and attach a real `.html` file instead of pasting source into Telegram.
    - [x] Recognize typo-style HTML creation requests already covered by the document parser.
    - [ ] Add browser render smoke for generated HTML files when the browser runtime is available.

### Unified Document Creation Across iMac And Telegram

- [x] **19.8. Canonical Document Router**
    - [x] Keep `DocumentActionRouter` as the canonical path for Markdown, HTML, Word, Excel, and PowerPoint creation.
    - [x] Keep Telegram text document requests on `DocumentActionRouter`.
    - [x] Keep Telegram voice document requests flowing through xAI STT, then `DocumentActionRouter`.
    - [x] Keep iMac document requests on `DocumentActionRouter` through the normal command route.
    - [x] Route the older iMac presentation shortcut into `DocumentActionRouter` instead of its old local-only PPTX shortcut.
    - [x] Keep network troubleshooting as a special local diagnostic workflow, but run Word artifact QA on its generated `.docx`.
    - [ ] Move remaining special document-producing workflows into a shared builder interface instead of letting each workflow hand-roll final delivery.

- [x] **19.9. Channel-Specific Delivery Only**
    - [x] iMac delivery opens or focuses the native app when appropriate.
    - [x] Telegram delivery attaches generated files.
    - [x] Latest-document path is recorded for created artifacts.
    - [x] Structured artifacts are recorded for direct document actions.
    - [x] Telegram last-document replies should keep important paths visible as text instead of only voice.
    - [ ] Add a regression that asks for the last document by voice and verifies Telegram includes path text plus a useful summary.

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
    - [ ] Add a real migration command that reports dedupe counts and links old rows to canonical IDs instead of only backfilling active facts.

### Memory Activation Rules

- [x] **19.12. First Activation Layer**
    - [x] Inject relevant canonical memories into prompt context as `Saved facts`.
    - [x] Keep pinned canonical memories eligible for stronger activation.
    - [x] Keep temporary test memories from activating unless query-relevant.
    - [x] Keep expired or forgotten canonical memory out of recall.
    - [x] Keep direct memory answers honest: if canonical memory has no active answer, Maya says she does not have it saved.
    - [ ] Add scoring decay based on age and reinforcement count.
    - [ ] Add explicit pin/unpin commands for canonical memories.
    - [ ] Add a direct inspector that shows canonical memory IDs and activation class.

### Weekly Memory Distillation

- [x] **19.13. Canonical Weekly Input**
    - [x] Weekly memory dry run backfills canonical memories before summarizing.
    - [x] Weekly memory samples active non-temporary canonical memories.
    - [x] Weekly memory excludes temporary and test-marker memories by default.
    - [x] Weekly summary reports canonical memory counts and canonical fact signals.
    - [ ] Make live weekly provider distillation write new stable memories through canonical memory only.
    - [ ] Record canonical memory IDs used in each weekly summary.
    - [ ] Add Claude weekly memory review for overreach, false assumptions, unsafe memory, and confirmation-needed facts.

### Regression Tests

- [x] **19.14. Local Smoke Coverage**
    - [x] Add artifact quality smoke test.
    - [x] Add canonical memory smoke test.
    - [x] Add both new smokes to `may1_rehearsal.py`.
    - [x] Update existing document smoke expectations for the new QA route labels.
    - [x] Run document, artifact quality, canonical memory, memory control, learning, weekly memory, Telegram routing, and iMac workflow smokes together.

- [ ] **19.15. Manual Telegram/iMac Regression**
    - [ ] Telegram text: create Word, Excel, PowerPoint, and HTML files; verify attachments, routes, costs, paths, and file quality.
    - [ ] Telegram voice: create one document by voice; verify STT, route, cost, attachment, visible path text, and voice reply behavior.
    - [ ] iMac text/voice: create one Word, Excel, PowerPoint, and HTML artifact; verify native app opening and same quality path.
    - [ ] Memory: save, recall, forget, and recall-again for one temporary test fact and one normal preference.
    - [ ] Weekly memory: dry run after temporary tests and verify test facts do not become durable weekly memory.
    - [x] Disable `ENABLE_LOCAL_WAKE_SCORER` for live use.
    - [x] Keep local wake experiments separate from paid Grok and out of the live path.
    - [x] Add voice device intent policy: Sony or `Zainal’s Headphone` allows Maya wake.
    - [x] Block AirPods and iMac audio from local Maya wake.
    - [x] Record Mudra within radius plus pinch as the future iMac-speaker wake path.
    - [x] Add a no-Grok local voice integration smoke for wake acknowledgement.
    - [x] Add hotkey voice smoke for deliberate local trigger plus 5 second idle close.
    - [x] Add hotkey voice smoke for manual stop.
    - [x] Remove false-wake acceptance target because voice wake activation is removed.
    - [x] Remove wake detection acceptance target because voice wake activation is removed.
    - [x] Do not connect local wake to Maya. Mudra is the future trigger.
    - [x] Do not use xAI STT confirmation for the current one-stage headphone path.
    - [x] Avoid continuous long headphone capture because it can degrade media audio quality.

---
*Updated May 23, 2026*
