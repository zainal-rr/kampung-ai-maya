# Kampung AI iMac Voice Realtime Checklist

## Decision

1) [x] No voice wake activation.
2) [x] No `Hey Maya` wake path for live use.
3) [x] No always-listening microphone loop.
4) [x] Mudra Link will be the future first-choice trigger.
5) [x] `Option + Space` is the temporary manual trigger.
6) [x] `Option + Escape` is the manual stop.
7) [x] Telegram voice testing is for remote testing while away, not the local iMac voice path.

## Realtime xAI Session

1) [x] Use xAI realtime websocket.
2) [x] Use `grok-voice-latest` as the voice model.
3) [x] Use `Ara` as Maya voice.
4) [x] Use 24 kHz raw PCM.
5) [x] Use server VAD.
6) [x] Add `input_audio_transcription` with `grok-2-audio`.
7) [ ] Support optional `web_search` and `x_search` tools only when approved.
8) [ ] Handle `session.created`.
9) [x] Handle `session.updated`.
10) [x] Do not send buffered audio until `session.updated`.

## Manual Trigger Flow

1) [x] `Option + Space` starts the session.
2) [x] Mic stays closed before `Option + Space`.
3) [x] Mic capture starts in parallel with websocket connect.
4) [x] Audio is buffered while websocket/session initializes.
5) [x] Buffered audio flushes after `session.updated`.
6) [x] `Option + Escape` requests session stop.
7) [ ] Stop key closes mic stream.
8) [ ] Stop key clears playback queue.
9) [ ] Stop key closes websocket.
10) [ ] Stop key resets session state.

## Interruption

1) [x] Handle `input_audio_buffer.speech_started`.
2) [x] Stop current playback immediately on speech start.
3) [x] Clear queued playback audio on speech start.
4) [x] Send `response.cancel` on speech start.
5) [ ] Continue listening after interruption.

## Playback

1) [x] Route output to `Zainal’s Headphone` or Sony MX5.
2) [ ] Keep iMac speaker from being selected unless explicitly configured.
3) [x] Stream output audio chunks instead of waiting for full WAV.
4) [ ] Playback must not block hotkey stop.
5) [ ] Playback must stop cleanly on manual stop.

## Context

1) [x] Inject Maya identity.
2) [x] Inject Malaysia time.
3) [x] Inject Kampung AI memory and preferences.
4) [x] Enforce no exclamation marks.
5) [x] Enforce no dash symbols unless technically required.
6) [x] Enforce language mirroring.
7) [ ] Confirm Grok can answer questions about saved preferences.

## Removed Future Direction

1) [ ] Remove voice wake activation language from `KAMPUNG_AI.md`.
2) [ ] Remove voice wake activation tasks from `KAMPUNG_AI_CHECKLIST.md`.
3) [ ] Remove voice wake activation tasks from `KAMPUNG_AI_PRE_TRAVEL_TEST_CHECKLIST.md`.
4) [ ] Remove voice wake activation tasks from `MAY_1_LAUNCH_RUNBOOK.md`.
5) [ ] Set `ENABLE_LOCAL_WAKE_SCORER=0`.
6) [ ] Set `ENABLE_XAI_WAKE_STT=0`.
7) [ ] Keep wakeword scripts only as archived experiments.

## Tests

1) [x] `hotkey_voice_channel_smoke.py`.
2) [x] `xai_realtime_stream_smoke.py`.
3) [ ] Manual hotkey starts session.
4) [ ] Manual stop reliably ends session.
5) [ ] Output goes to headphones.
6) [ ] Maya answers Malaysia time correctly.
7) [ ] Maya answers preference questions from Kampung AI memory.
8) [ ] `code_health.py`.
