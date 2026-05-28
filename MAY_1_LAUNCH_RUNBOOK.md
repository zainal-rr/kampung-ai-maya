# May 20 Launch Runbook

Use this on May 20, 2026 when the remaining API keys arrive. The goal is to prove each lane first, then turn on the fuller Maya loop. Mudra Link and the Omi band are expected to be ordered around this same window, with hardware integration likely after they arrive.

## 1. Starting Posture

Keep the system conservative before the keys are tested.

1) `ENABLE_IMAC_CHANNEL=0`
2) `TELEGRAM_VOICE_REPLIES=1`
3) `TELEGRAM_REQUIRE_ARA=1`
4) `TELEGRAM_VOICE_LOCKED=1`
5) `TELEGRAM_ROUTINE_AUDIO=0`
6) `ENABLE_ARCHIVE_MEMORY=0`
7) `ENABLE_OMI_ADAPTER=0`
8) `ENABLE_MUDRA_ADAPTER=0`
9) `ENABLE_AGENT_RUNTIME=1`
10) `ENABLE_ROUTINES=1`
11) `XAI_VOICE_AGENT_IDLE_SECONDS=5`
12) `ENABLE_XAI_VOICE_AGENT=0` until the dedicated live speech-to-speech path is tested.
13) `ENABLE_OMI_ADAPTER=0` and `ENABLE_MUDRA_ADAPTER=0` stay off until the real hardware is present.

## 2. Add Keys

Edit `/Users/zainalabidinjamal/projects/kampung-ai/.env`.

1) Add `OPENAI_API_KEY` for Maya's strategic lane.
2) Add `XAI_API_KEY` for Grok Voice Agent, Ara voice notes, xAI STT, and pulse/news.
3) Confirm `GOOGLE_API_KEY`, `KIMI_API_KEY`, and `TELEGRAM_BOT_TOKEN` are still present.

Do not paste keys into Telegram, logs, screenshots, or checklist files.

## 3. Hardware Order Window

Mudra Link and the Omi band are not blockers for May 20 API-key testing.

1) Order Mudra Link around May 20, 2026.
2) Order Omi band around May 20, 2026.
3) Expect a 2 to 3 week wait after ordering.
4) Treat June 3 to June 10, 2026 as the likely first hardware integration window.
5) Keep both adapters in staging mode until the real devices and transcript flow are present.

## 4. First Checks

Run the local rehearsal from the project directory first.

```bash
/Users/zainalabidinjamal/projects/kampung-ai/venv/bin/python may1_rehearsal.py
```

After the keys are added, run the live checks.

```bash
/Users/zainalabidinjamal/projects/kampung-ai/venv/bin/python doctor.py
/Users/zainalabidinjamal/projects/kampung-ai/venv/bin/python screen_probe.py
/Users/zainalabidinjamal/projects/kampung-ai/venv/bin/python app_interaction_smoke.py
/Users/zainalabidinjamal/projects/kampung-ai/venv/bin/python browser_control_smoke.py
/Users/zainalabidinjamal/projects/kampung-ai/venv/bin/python web_actions_smoke.py
/Users/zainalabidinjamal/projects/kampung-ai/venv/bin/python imac_workflows_smoke.py
/Users/zainalabidinjamal/projects/kampung-ai/venv/bin/python delivery_redaction_smoke.py
/Users/zainalabidinjamal/projects/kampung-ai/venv/bin/python permission_policy_smoke.py
/Users/zainalabidinjamal/projects/kampung-ai/venv/bin/python screen_answer_probe.py "Can you see what i open in chrome?"
/Users/zainalabidinjamal/projects/kampung-ai/venv/bin/python learning_smoke.py
/Users/zainalabidinjamal/projects/kampung-ai/venv/bin/python provider_smoke.py
/Users/zainalabidinjamal/projects/kampung-ai/venv/bin/python may1_rehearsal.py --live-providers
```

Expected posture:

1) `doctor.py` shows required keys set and Telegram ready.
2) `learning_smoke.py` prints `learning_smoke: ok`.
3) `provider_smoke.py` loads `.env`, reports key status, and checks Gemini, GPT-5.5, Kimi, Grok, Ara TTS, and xAI STT.
4) Ara TTS is only counted when the xAI API succeeds. Local macOS voice fallback does not count as Ara.
5) `screen_answer_probe.py` can bring Chrome forward and describe the visible active tab.
6) `app_interaction_smoke.py` confirms app switching, shortcuts, typed text routing, and local folder access including Desktop.
7) `browser_control_smoke.py` confirms active-page inspection and visible-text browser clicking.
8) `web_actions_smoke.py` confirms web search and travel research open the browser while booking and payment stay guarded.
9) `imac_workflows_smoke.py` confirms guided flight, browser inspect/click, presentation, and network-document workflows.
10) `workspace_drawing_smoke.py` confirms folder/project creation and drawing delivery.
11) `permission_policy_smoke.py` confirms create/write file allowance, browser research, browser click boundaries, document/presentation work, Cloudflare/GCP allowance, delete/send confirmation, booking/payment confirmation, and sensitive private exposure blocking.
12) `delivery_redaction_smoke.py` confirms Telegram and iMac preserve visible app names while external destinations redact.
13) `session_compactor_smoke.py` confirms token-aware shared context, topic continuity, and separate hard-fact injection.
14) `telegram_delivery_file_smoke.py` confirms long Telegram text splitting and generated-file delivery.

## 5. Restart Runtime

After the smoke checks pass:

```bash
/Users/zainalabidinjamal/projects/kampung-ai/venv/bin/python service_install.py
```

Then check:

```bash
/Users/zainalabidinjamal/projects/kampung-ai/venv/bin/python doctor.py
```

## 6. Telegram Tests

Use `KAMPUNG_AI_LIVE_API_TEST_CHECKLIST.md` as the detailed checklist for live lane testing. The list below is the broad runbook sequence.

Send these in Telegram.

1) `hello maya` as a normal text greeting
2) `tell me my preference`
3) `Remember that Telegram replies should stay short unless the task is complex`
4) `what did you learn from me today`
5) `what AI is powering you now`
6) `what can you do for me on Telegram right now`
7) `/complex help me think through Kampung AI architecture`
8) `/cost`
9) `/route`
10) `/screen`
11) `What apps are open?`
12) `Can you see what is in Safari?`
13) `Can you see what I open in Chrome?`

Maya should answer as one person, keep provider names hidden, keep replies concise, and only claim saved memory after write verification.

## 7. Voice Tests

Only after text and provider smoke pass:

1) Keep `TELEGRAM_VOICE_REPLIES=1`, `TELEGRAM_REQUIRE_ARA=1`, and `TELEGRAM_VOICE_LOCKED=1`.
2) Send a short Telegram prompt and confirm the voice note sounds like Ara.
3) Send a short Telegram voice note and confirm it routes like typed Telegram text.
4) Keep `ENABLE_IMAC_CHANNEL=0` while wake detection is still being hardened.
5) Keep the old `ffmpeg` file-capture hotkey path as diagnostic only. It proved too clunky for natural iMac voice.
6) Next local voice implementation should use `Option + Space` to open a realtime Grok Voice Agent websocket session.
7) Stream microphone audio chunks to Grok, use server-side turn detection, and stream Ara audio back as it arrives.
8) Press `Option + Escape` if the streaming session should stop immediately.
9) Do not use always-on voice wake for the pre-travel test window. Mudra pinch becomes the preferred physical manual trigger after hardware arrives. No voice wake activation.
10) If realtime local voice is not ready, keep testing through Telegram and leave the iMac voice path off.

## 8. Travel Testing Window: 25 May to 8 June 2026

Use `KAMPUNG_AI_TRAVEL_TEST_CHECKLIST.md` while Zainal is away from the iMac.

1) Keep the iMac powered on and connected.
2) Treat Telegram as the main live testing surface.
3) Use Codex mobile only for debugging if Telegram reveals a bug.
4) Use Splashtop Streamer as the remote iMac maintenance path for restarts, visual file checks, and confirming the machine is online.
5) Do not treat Splashtop audio as proof that the local iMac speech-to-speech path is good.
6) Do not actively test local iMac speech-to-speech while away.
7) Avoid `/screen` and `/see` unless intentionally checking the remote iMac state.
8) Keep `ENABLE_OMI_ADAPTER=0` and `ENABLE_MUDRA_ADAPTER=0` until the real hardware is present and Zainal is back.
9) If local iMac voice is not fully stable before leaving, keep `ENABLE_XAI_VOICE_AGENT=0` during the away window.
10) Capture Maya's reply, `/route`, `/status`, and any generated file when a remote test behaves oddly.

## 9. Rollback

If anything feels unstable:

1) Set `ENABLE_IMAC_CHANNEL=0`.
2) Keep Telegram text working. If Ara delivery fails badly, set `TELEGRAM_VOICE_REPLIES=0` temporarily and log it as a voice-lane issue.
3) Keep `ENABLE_AGENT_RUNTIME=1` if reminders and health are stable.
4) Re-run `doctor.py`.
5) Check `/Users/zainalabidinjamal/projects/kampung-ai/logs/error.log`.

## 10. Go-Live Rule

Maya is live only when these are true:

1) `doctor.py` is clean enough for the intended mode.
2) `provider_smoke.py` passes for the lanes being enabled.
3) `learning_smoke.py` passes.
4) Telegram replies feel fast and natural.
5) The iMac voice loop is enabled only after manual-trigger Grok Voice Agent speech-to-speech and Ara output are proven.
