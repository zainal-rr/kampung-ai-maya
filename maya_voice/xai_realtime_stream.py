from __future__ import annotations

import asyncio
import contextlib
import json
import os
import time

import sounddevice as sd
import websockets

from maya_core.cost_tracker import record_usage
from maya_core.route_tracker import record_route
from maya_core.session_memory_actions import save_voice_session_summary
from maya_core.sounddevice_audio import (
    output_device_snapshot,
    refresh_sounddevice_hostapi,
    resolve_first_output,
    resolve_first_output_name,
    resolve_sounddevice_input_after_refresh,
)
from maya_voice.voice_session_log import finish_voice_session, start_voice_session
from maya_voice.xai_realtime_audio_math import pcm_rms
from maya_voice.xai_realtime_stream_helpers import append_audio_message, put_latest, put_playback
from maya_voice.xai_voice_agent import realtime_url
from maya_voice.xai_realtime_events import XaiRealtimeEventMixin
from maya_voice.xai_realtime_models import PlaybackCommand, SessionCloseReason
from maya_voice.xai_realtime_playback import XaiRealtimePlaybackMixin
from maya_voice.xai_realtime_session_update import session_update_payload


class XaiRealtimeStreamingSession(XaiRealtimeEventMixin, XaiRealtimePlaybackMixin):
    def __init__(self, db_path: str, instructions: str, stop_event: asyncio.Event | None = None, *, assistant=None):
        self.db_path = db_path
        self.assistant = assistant
        self.instructions = instructions
        self.stop_event = stop_event or asyncio.Event()
        self.sample_rate = int(os.getenv("XAI_VOICE_AGENT_SAMPLE_RATE", "24000"))
        self.blocksize = int(os.getenv("XAI_VOICE_STREAM_BLOCKSIZE", "2400"))
        self.input_device = resolve_sounddevice_input_after_refresh()
        self.output_device, self.output_device_name = resolve_first_output_name()
        self.started_at = 0.0
        self.websocket = None
        self.audio_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=16)
        self.session_ready = asyncio.Event()
        self.pending_audio: list[bytes] = []
        self.max_pending_chunks = int(os.getenv("XAI_VOICE_PENDING_AUDIO_CHUNKS", "100"))
        self.playback_queue: asyncio.Queue[PlaybackCommand] = asyncio.Queue(maxsize=32)
        self.response_active = False
        self.playback_prebuffer_ms = int(os.getenv("XAI_VOICE_PLAYBACK_PREBUFFER_MS", "800"))
        self.transcripts: list[str] = []
        self.last_underrun_log = 0.0
        self.current_output = None
        self.drop_audio_until_next_response = False
        self.underrun_logged_for_response = False
        self.last_output_route_warning = ""
        self.idle_seconds = float(os.getenv("XAI_VOICE_AGENT_IDLE_SECONDS", "20"))
        self.last_activity_at = time.monotonic()
        self.output_started_at = 0.0
        self.close_reason = SessionCloseReason.RUNNING
        self.audio_error_count = 0
        self.output_reset_count = 0
        self.input_chunks_captured = 0
        self.input_chunks_sent = 0
        self.input_bytes_sent = 0
        self.last_input_audio_at = 0.0
        self.last_local_mic_rms = 0.0
        self.peak_local_mic_rms = 0.0
        self.peak_local_mic_rms_since_response = 0.0
        self.peak_local_mic_rms_since_response_at = 0.0
        self.last_xai_speech_started_at = 0.0
        self.last_user_transcript_at = 0.0
        self.last_response_done_at = 0.0
        self.last_vad_silent_log_at = 0.0
        self.vad_silent_logged_for_response = False
        self.vad_silent_rms_threshold = float(os.getenv("XAI_VOICE_VAD_SILENT_RMS_THRESHOLD", "900"))
        self.vad_silent_delay_seconds = float(os.getenv("XAI_VOICE_VAD_SILENT_DELAY_SECONDS", "2.5"))
        self.fragment_response_suppression_until = 0.0
        self.fragment_response_text = ""
        self.fragment_response_suppression_seconds = float(os.getenv("XAI_VOICE_FRAGMENT_SUPPRESSION_SECONDS", "3.0"))
        self.voice_log_session_id: int | None = None
        self.current_response_id = ""
        self.tool_calls_by_response: dict[str, set[str]] = {}
        self.assistant_transcript_parts: list[str] = []
        self.assistant_transcript_recorded = False
        self.function_call_tasks: set[asyncio.Task] = set()
        self.supervised_voice_work_request = ""
        self.supervised_voice_work_tool_name = ""
        self.supervised_voice_work_kind = ""
        self.supervised_voice_work_ack = ""
        self.supervised_voice_work_id = ""
        self.supervised_voice_work_followups: list[str] = []
        self.supervised_voice_work_steer_events: list[dict] = []
        self.supervised_voice_work_applied_followup_count = 0
        self.supervised_voice_work_execution_started = False
        self.supervised_voice_work_suppress_until = 0.0
        self.supervised_voice_work_auto_cancel_until = 0.0
        self.supervised_voice_work_auto_cancelled = False
        self.supervised_voice_work_ack_pending = False
        self.supervised_voice_work_task: asyncio.Task | None = None
        self.supervised_browser_request = ""
        self.supervised_browser_suppress_until = 0.0
        self.supervised_browser_task: asyncio.Task | None = None

    async def run(self) -> None:
        self.started_at = time.monotonic()
        self._require_configured_input_available()
        await record_route(self.db_path, "voice", "Grok Voice Agent streaming", "manual hotkey", True)
        try:
            self.voice_log_session_id = await start_voice_session(
                self.db_path,
                input_device=str(self.input_device),
                output_device=self.output_device_name,
                sample_rate=self.sample_rate,
                model=os.getenv("XAI_VOICE_AGENT_MODEL", "grok-voice-latest"),
                voice=os.getenv("XAI_VOICE_AGENT_VOICE", "ara"),
            )
        except Exception as exc:
            print(f"maya-hotkey-voice-log-error> start failed: {exc}", flush=True)
        print(
            "maya-hotkey-runtime> voice_tool_seam=tool_call_only "
            "transcript_auto_start=disabled local_guard=empty_only_safety "
            "clarification_style=open_question_no_examples",
            flush=True,
        )
        try:
            async with await self._connect_websocket() as websocket:
                self.websocket = websocket
                await websocket.send(json.dumps(self._session_update()))
                tasks = [
                    asyncio.create_task(self._stream_input()),
                    asyncio.create_task(self._receive_events()),
                    asyncio.create_task(self._play_output()),
                ]
                if self.idle_seconds > 0:
                    tasks.append(asyncio.create_task(self._idle_watchdog()))
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in pending:
                    task.cancel()
                for task in pending:
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
                for task in done:
                    task.result()
                if self.close_reason == SessionCloseReason.RUNNING:
                    self.close_reason = SessionCloseReason.COMPLETED
        except asyncio.TimeoutError:
            self.close_reason = SessionCloseReason.WEBSOCKET_TIMEOUT
            raise
        except Exception:
            if self.close_reason == SessionCloseReason.RUNNING:
                self.close_reason = SessionCloseReason.ERROR
            raise
        finally:
            duration = max(0.0, time.monotonic() - self.started_at)
            await self._record_pending_assistant_transcript(interrupted=False)
            await save_voice_session_summary(self.db_path, self.transcripts)
            export_path = ""
            try:
                export_path = await finish_voice_session(
                    self.db_path,
                    self.voice_log_session_id,
                    close_reason=self.close_reason.value,
                    duration_seconds=duration,
                    input_device=str(self.input_device),
                    output_device=self.output_device_name,
                    audio_error_count=self.audio_error_count,
                    output_reset_count=self.output_reset_count,
                    input_chunks_captured=self.input_chunks_captured,
                    input_chunks_sent=self.input_chunks_sent,
                    input_bytes_sent=self.input_bytes_sent,
                    last_input_audio_at=self._elapsed(self.last_input_audio_at),
                    last_local_mic_rms=self.last_local_mic_rms,
                    peak_local_mic_rms=self.peak_local_mic_rms,
                    peak_local_mic_rms_since_response=self.peak_local_mic_rms_since_response,
                    peak_local_mic_rms_since_response_at=self._elapsed(self.peak_local_mic_rms_since_response_at),
                    last_xai_speech_started_at=self._elapsed(self.last_xai_speech_started_at),
                    last_user_transcript_at=self._elapsed(self.last_user_transcript_at),
                    last_response_done_at=self._elapsed(self.last_response_done_at),
                    transcript_count=len(self.transcripts),
                )
            except Exception as exc:
                print(f"maya-hotkey-voice-log-error> finish failed: {exc}", flush=True)
            await record_usage(self.db_path, "grok_voice_agent_seconds", duration, "manual streaming hotkey")
            print(
                f"maya-hotkey-session-closed> reason={self.close_reason.value} "
                f"audio_errors={self.audio_error_count} output_resets={self.output_reset_count} "
                f"input_chunks={self.input_chunks_captured}/{self.input_chunks_sent} "
                f"transcripts={len(self.transcripts)} duration={duration:.1f}s "
                f"export={export_path}",
                flush=True,
            )

    async def _connect_websocket(self):
        last_exc: Exception | None = None
        attempts = max(1, int(os.getenv("XAI_VOICE_CONNECT_ATTEMPTS", "1")))
        open_timeout = float(os.getenv("XAI_VOICE_OPEN_TIMEOUT_SECONDS", "6"))
        for attempt in range(1, attempts + 1):
            try:
                return await websockets.connect(
                    realtime_url(),
                    additional_headers={"Authorization": f"Bearer {os.environ['XAI_API_KEY']}"},
                    open_timeout=open_timeout,
                )
            except Exception as exc:
                last_exc = exc
                if attempt >= attempts:
                    break
                print(f"maya-hotkey-connect-note> websocket open failed, retrying once: {exc}", flush=True)
                await asyncio.sleep(1)
        raise last_exc or RuntimeError("Could not open xAI realtime websocket.")

    def _require_configured_input_available(self) -> None:
        if self.input_device is not None:
            return
        if os.getenv("IMAC_AUDIO_REQUIRE_CONFIGURED_INPUT", "0") != "1":
            return
        configured = os.getenv("IMAC_AUDIO_INPUT_NAMES") or os.getenv("IMAC_AUDIO_INPUT") or "configured input"
        self.close_reason = SessionCloseReason.INPUT_ERROR
        print(f"maya-hotkey-input-unavailable> configured microphone is unavailable: {configured}", flush=True)
        raise RuntimeError(f"Configured microphone is unavailable: {configured}")

    async def stop(self) -> None:
        if self.close_reason == SessionCloseReason.RUNNING:
            self.close_reason = SessionCloseReason.MANUAL_STOP
        print("maya-hotkey> hard stop requested", flush=True)
        self.stop_event.set()
        await self._clear_playback_queue()
        await put_playback(self.playback_queue, PlaybackCommand("interrupt"))
        await put_playback(self.playback_queue, PlaybackCommand("shutdown"))
        if self.websocket:
            with contextlib.suppress(Exception):
                if self.response_active:
                    await self.websocket.send(json.dumps({"type": "response.cancel"}))
            with contextlib.suppress(Exception):
                await self.websocket.close()

    def _session_update(self) -> dict:
        return session_update_payload(self.instructions, self.sample_rate)

    async def _stream_input(self) -> None:
        loop = asyncio.get_running_loop()

        def callback(indata, frames, time_info, status):
            if self.stop_event.is_set():
                return
            data = bytes(indata)
            self.input_chunks_captured += 1
            self.last_input_audio_at = time.monotonic()
            self.last_local_mic_rms = pcm_rms(data)
            self.peak_local_mic_rms = max(self.peak_local_mic_rms, self.last_local_mic_rms)
            if self.last_response_done_at and self.last_input_audio_at >= self.last_response_done_at:
                if self.last_local_mic_rms > self.peak_local_mic_rms_since_response:
                    self.peak_local_mic_rms_since_response = self.last_local_mic_rms
                    self.peak_local_mic_rms_since_response_at = self.last_input_audio_at
            loop.call_soon_threadsafe(put_latest, self.audio_queue, data)

        with self._open_input_stream(callback):
            while not self.stop_event.is_set():
                audio = await self.audio_queue.get()
                if self.stop_event.is_set():
                    break
                if not self.session_ready.is_set():
                    self._buffer_audio(audio)
                    continue
                self._mark_input_sent(audio)
                await self.websocket.send(json.dumps(append_audio_message(audio)))

    def _open_input_stream(self, callback):
        refresh_sounddevice_hostapi()
        if self.input_device is None and os.getenv("IMAC_AUDIO_REQUIRE_CONFIGURED_INPUT", "0") == "1":
            configured = os.getenv("IMAC_AUDIO_INPUT_NAMES") or os.getenv("IMAC_AUDIO_INPUT") or "configured input"
            raise RuntimeError(f"Configured microphone is unavailable: {configured}")
        try:
            stream = sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=self.blocksize,
                device=self.input_device,
                channels=1,
                dtype="int16",
                callback=callback,
            )
            print(f"maya-hotkey> input opened: {self.input_device}", flush=True)
            return stream
        except Exception as exc:
            print(f"maya-hotkey-input-error> {exc}; refreshing PortAudio and retrying once", flush=True)
            refresh_sounddevice_hostapi()
            self.input_device = resolve_sounddevice_input_after_refresh()
            stream = sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=self.blocksize,
                device=self.input_device,
                channels=1,
                dtype="int16",
                callback=callback,
            )
            print(f"maya-hotkey> input opened after retry: {self.input_device}", flush=True)
            return stream

    def _mark_input_sent(self, audio: bytes) -> None:
        self.input_chunks_sent += 1
        self.input_bytes_sent += len(audio)

    def _elapsed(self, timestamp: float) -> float:
        if not timestamp or not self.started_at:
            return 0.0
        return round(max(0.0, timestamp - self.started_at), 3)
