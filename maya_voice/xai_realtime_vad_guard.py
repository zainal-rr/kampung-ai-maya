from __future__ import annotations

import asyncio
import contextlib
import json
import time

from maya_voice.voice_session_log import record_voice_turn
from maya_voice.xai_realtime_models import PlaybackCommand, SessionCloseReason
from maya_voice.xai_realtime_stream_helpers import put_playback


class XaiRealtimeVadGuardMixin:
    async def _idle_watchdog(self) -> None:
        while not self.stop_event.is_set():
            await asyncio.sleep(0.5)
            if not self.session_ready.is_set() or self.response_active:
                continue
            await self._log_vad_silent_if_needed()
            if time.monotonic() - self.last_activity_at >= self.idle_seconds:
                print(f"maya-hotkey> idle timeout after {self.idle_seconds:g}s", flush=True)
                self.close_reason = SessionCloseReason.IDLE
                await self.stop()
                break

    def _touch_activity(self) -> None:
        self.last_activity_at = time.monotonic()

    async def _log_vad_silent_if_needed(self) -> None:
        if self.vad_silent_logged_for_response or not self.last_response_done_at:
            return
        now = time.monotonic()
        rms_threshold = float(getattr(self, "vad_silent_rms_threshold", 0) or 900.0)
        delay_seconds = float(getattr(self, "vad_silent_delay_seconds", 0) or 2.5)
        if now - self.last_response_done_at < delay_seconds or now - self.last_input_audio_at > 1.0:
            return
        peak = max(self.last_local_mic_rms, self.peak_local_mic_rms_since_response)
        if peak < rms_threshold:
            return
        recent_xai_speech = self.last_xai_speech_started_at and now - self.last_xai_speech_started_at < delay_seconds
        recent_transcript = self.last_user_transcript_at and now - self.last_user_transcript_at < delay_seconds
        if recent_xai_speech or recent_transcript:
            return
        self.vad_silent_logged_for_response = True
        self.last_vad_silent_log_at = now
        message = "Local mic audio is present after Maya responded, but xAI has not emitted speech_started or a transcript."
        print(f"maya-hotkey-vad-note> {message} peak_rms={peak}", flush=True)
        await record_voice_turn(
            self.db_path,
            self.voice_log_session_id,
            "system",
            message,
            event_type="vad_silent_after_response",
            response_id=self.current_response_id,
            diagnostics={
                "last_local_mic_rms": self.last_local_mic_rms,
                "peak_local_mic_rms_since_response": self.peak_local_mic_rms_since_response,
                "peak_local_mic_rms_since_response_at": round(self.peak_local_mic_rms_since_response_at - self.started_at, 3)
                if self.peak_local_mic_rms_since_response_at and self.started_at
                else 0,
                "input_chunks_captured": self.input_chunks_captured,
                "input_chunks_sent": self.input_chunks_sent,
                "seconds_since_response_done": round(now - self.last_response_done_at, 3),
            },
        )

    def _update_fragment_response_guard(self, transcript: str) -> None:
        if self._looks_like_incomplete_fragment(transcript):
            self.fragment_response_text = transcript.strip()
            self.fragment_response_suppression_until = time.monotonic() + self.fragment_response_suppression_seconds
            print(f"maya-hotkey-fragment-note> waiting for more speech after fragment: {self.fragment_response_text}", flush=True)
            return
        self.fragment_response_text = ""
        self.fragment_response_suppression_until = 0.0

    async def _cancel_incomplete_fragment_response(self) -> bool:
        if not self.fragment_response_text or time.monotonic() > self.fragment_response_suppression_until:
            return False
        self.drop_audio_until_next_response = True
        await self._clear_playback_queue()
        if self.websocket:
            with contextlib.suppress(Exception):
                await self.websocket.send(json.dumps({"type": "response.cancel"}))
        await record_voice_turn(
            self.db_path,
            self.voice_log_session_id,
            "system",
            f"Suppressed immediate Maya response to incomplete speech fragment: {self.fragment_response_text}",
            event_type="incomplete_fragment_response_suppressed",
            response_id=self.current_response_id,
            diagnostics={"fragment": self.fragment_response_text},
        )
        print(f"maya-hotkey-fragment-note> suppressed response to fragment: {self.fragment_response_text}", flush=True)
        self.response_active = False
        self.current_response_id = ""
        await put_playback(self.playback_queue, PlaybackCommand("end_response"))
        return True

    @staticmethod
    def _looks_like_incomplete_fragment(transcript: str) -> bool:
        cleaned = " ".join(transcript.casefold().replace(",", " ").replace(".", " ").split())
        if not cleaned:
            return False
        words = cleaned.split()
        if len(words) > 3:
            return False
        exact_fragments = {
            "um", "uh", "er", "erm", "hmm", "ah", "i", "i am", "i'm", "i was", "i want",
            "i need", "i have", "um i", "uh i", "er i", "so", "so i", "can you", "could you", "maya can",
        }
        return cleaned in exact_fragments or words[0] in {"um", "uh", "er", "erm", "hmm", "ah"}
