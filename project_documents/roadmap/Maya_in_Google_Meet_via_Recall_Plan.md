# Maya in Google Meet via Recall.ai — Integration Plan
*Goal: Maya joins a Google Meet as a spoken, acting participant — a teammate people talk to, who answers and takes real action — not a silent notetaker.*

## Mental model
Recall.ai is a new **pair of ears and a mouth** bolted onto the Maya brain you already have. You are not rebuilding Maya; you are swapping where her audio comes from and goes to. Everything that makes her *Maya* — the decide-and-act core, phases, verified-facts narration, browser/doc actions, safety, honesty — sits untouched behind that seam.

There are two planes to wire.

## 1. Control plane (the easy part)
- Call Recall's API to send a bot into a given meeting URL.
- Stand up a **webhook receiver** for bot lifecycle events (joined, participants, left) and, optionally, transcription events.
- Maya already runs servers (the extension bridge, the UI SSE server), so adding a webhook listener is not new ground.
- This is the "Maya, join *this* Meet" wiring — just HTTP plus a small receiver.

## 2. Media plane (the real work)
- **Ears:** subscribe to Recall's real-time audio stream from the meeting (or its live transcription). Raw audio → Maya's realtime model is lower-latency and enables barge-in; Recall's transcription is simpler but adds delay and loses prosody. For a conversational teammate, prefer the raw-audio path.
- **Mouth:** Maya's synthesized speech is pushed to Recall's output-audio channel; Recall injects it into the call as the bot's voice.

### The seam that matters
Today Maya's realtime loop binds to a **local mic (in)** and **speaker (out)**. The whole integration is replacing those two endpoints:
- `local mic → Recall meeting-audio stream`
- `local speaker → Recall output-audio`

behind the same interface. If her voice loop already abstracts the audio source/sink (or you make it), that adapter *is* the integration on Maya's side. **This is the same audio-decoupling work as containerizing voice / VM hosting — so it's synergistic, not a detour.**

## 3. Topology choice
- **Pipe:** Recall audio → STT → Maya's text brain → TTS → Recall out. Provider-agnostic, more parts, more latency.
- **Realtime-model bridge:** Recall audio → straight into the realtime speech model Maya already uses (Grok realtime) → its audio out → Recall out. Lowest latency; the fiddly part is bridging two live WebSocket audio streams. **Since Maya already runs on a realtime model, this is the natural fit** — and where most of the engineering effort lands.

## 4. Behavior: narrate-and-act teammate (already built)
Maya should acknowledge immediately and act in parallel ("give me a sec, opening that now"), like a colleague whose hands are already moving — not report after the fact like a tool. Her architecture already supports this:
- **Async voice-work with phases** (acknowledge → working → done) keeps the conversation alive while the action runs in a worker. (See the voice-work runtime / `run_browser_capability_isolated`.)
- **Narrate intention immediately, confirm completion only when verified.** This is already a closed disappointment-log item: D4 (acknowledge once, then report the final result) and D5 (don't claim success before the action is verified). Her verified-facts path is what stops "there you go!" from running ahead of reality.
- **Fail honestly, out loud** — narrate the failure instead of going silent (disappointment-log return-direction fix).
- **Interruptibility** — a teammate you can cut off mid-action; her existing cancellation path (`voice_work_cancel_requested`) becomes social grace in a meeting.

## 5. The hard parts (all in the media bridge, not the API calls)
- **Audio format plumbing** — sample rates, PCM frame sizes, resampling between Recall and the realtime model. Tedious, bounded.
- **Latency budget** — every hop (meeting → Recall → server → model → back → Recall → meeting) adds ms; conversational feel lives or dies here, which is why the bridge topology beats the pipe. Note: W2-B's weak-path recall added ~867ms; memory recall firing mid-meeting would stack on top — pre-warm/cache or gate it.
- **Barge-in across two systems** — detecting a human starting to talk (to stop Maya's TTS) now spans Recall's stream and the model's voice-activity detection. Coordinating the interrupt across both is the genuinely tricky engineering.
- **Speaker attribution** — Recall's per-participant labels are useful evidence, but not authority. M1 needs a separate owner-attribution mini-plan before Maya can treat any meeting speech as Zainal; until then, every meeting utterance defaults to `other_speaker`, so action requests and confirmations require owner approval.

## 6. The new risk axis: multi-party turn-taking
Every turn-taking/narration fix in the disappointment log (D4, D5, D7, D9) was tested **1:1** — you and Maya. A Meet adds an axis those never covered: **multiple human speakers and cross-talk.** Her turn detector is silence-based and tuned for one person's stutters; a four-person Meet is a different acoustic problem (who's talking, not stepping on a handoff, not treating a pause as her cue). This is the next disappointment-log entry waiting to be written, and the one thing only a live meeting can prove.

## 7. Safety/honesty get *more* load here (ties to W5/W7)
In a meeting, **other people become input and trigger sources** — anyone can speak a command, and shared-screen/chat content becomes an untrusted read surface. So:
- W5 (blast-radius/broker) and W7 (untrusted-input boundary) stop being "before more autonomy" and become "**before people who aren't you can talk to her.**"
- W7 fail-closed rule for M1: all Meet speech is `other_speaker`; Recall speaker labels are evidence only and never grant authority.
- M1 is passive: Maya answers only when directly addressed and no room speech can trigger tools.
- M2 uses owner voiceprint/speaker verification as the chosen attribution mechanism, but only for reversible meeting actions. Other people can ask; only Zainal acts.
- Meeting voice never authorizes irreversible/external actions such as send, delete, login, payment, booking, upload/export, repo writes, command execution, or file writes outside Maya scratch.
- Owner-private disclosure is separately gated even for verified owner voice: private memory/files/logs/docs go owner-channel-only unless possession-channel confirmation allows room disclosure.
- Voiceprint enrollment, re-enrollment, and revocation are root-of-trust operations and must come from an already trusted owner channel, never from meeting voice.
- The fail-honestly / verified-facts discipline matters most here: a live meeting is the max-embarrassment place to hallucinate. Better "I'm not sure, let me check" than a confident wrong answer in front of five people.

## 8. One thing to verify before building
The exact Recall endpoint names and whether **real-time audio *output*** (the bot speaking) is enabled on your plan should be confirmed in Recall's current docs / your dashboard — that's a fast-moving product. The architecture above is stable; the precise API surface is what you check.

## Connection in one line
A small adapter that lets Recall's meeting-audio stream stand in for Maya's mic and Recall's output-audio stand in for her speaker — plus a webhook receiver for "join this call." Everything that makes her Maya sits untouched behind that seam, and the audio-decoupling it requires is the same work that frees her voice for VM hosting. The Meet is the capstone demo; the seam underneath is infrastructure you needed anyway.

## Sequencing note
This rides on the same prerequisites as the rest of the roadmap: it stresses W5/W7 (other-people-as-input) and the multi-party turn-taking is unproven, so treat the live Meet as a *new thing to prove*, not a free extension of the desk-tested voice loop. M2 is not considered enabled until real voiceprint enrollment passes a measured false-accept/false-reject scorecard with recordings, non-owner samples, noise/cross-talk, and threshold tuning biased toward false reject.
