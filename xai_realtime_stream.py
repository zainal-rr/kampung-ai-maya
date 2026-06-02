from __future__ import annotations

import asyncio
import contextlib
import os
import time

import sounddevice as sd
import websockets

from cost_tracker import record_usage
from route_tracker import record_route
from session_memory_actions import save_voice_session_summary
from sounddevice_audio import (
    output_device_snapshot,
    refresh_sounddevice_hostapi,
    resolve_first_output,
    resolve_first_output_name,
    resolve_sounddevice_input,
)
from voice_session_log import finish_voice_session, start_voice_session
from xai_realtime_stream_helpers import append_audio_message, put_latest, put_playback
from xai_realtime_tools import voice_tools
from xai_voice_agent import realtime_url
from xai_realtime_events import XaiRealtimeEventMixin
from xai_realtime_models import PlaybackCommand, SessionCloseReason
from xai_realtime_playback import XaiRealtimePlaybackMixin


class XaiRealtimeStreamingSession(XaiRealtimeEventMixin, XaiRealtimePlaybackMixin):
    def __init__(self, db_path: str, instructions: str, stop_event: asyncio.Event | None = None):
        self.db_path = db_path
        self.instructions = instructions
        self.stop_event = stop_event or asyncio.Event()
        self.sample_rate = int(os.getenv("XAI_VOICE_AGENT_SAMPLE_RATE", "24000"))
        self.blocksize = int(os.getenv("XAI_VOICE_STREAM_BLOCKSIZE", "2400"))
        self.input_device = resolve_sounddevice_input()
        self.output_device, self.output_device_name = resolve_first_output_name()
        self.started_at = 0.0
        self.websocket = None
        self.audio_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=16)
        self.session_ready = asyncio.Event()
        self.pending_audio: list[bytes] = []
        self.max_pending_chunks = int(os.getenv("XAI_VOICE_PENDING_AUDIO_CHUNKS", "100"))
        self.playback_queue: asyncio.Queue[PlaybackCommand] = asyncio.Queue(maxsize=32)
        self.response_active = False
        self.playback_prebuffer_ms = int(os.getenv("XAI_VOICE_PLAYBACK_PREBUFFER_MS", "260"))
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
        self.voice_log_session_id: int | None = None
        self.current_response_id = ""
        self.assistant_transcript_parts: list[str] = []
        self.assistant_transcript_recorded = False

    async def run(self) -> None:
        self.started_at = time.monotonic()
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
                    transcript_count=len(self.transcripts),
                )
            except Exception as exc:
                print(f"maya-hotkey-voice-log-error> finish failed: {exc}", flush=True)
            await record_usage(self.db_path, "grok_voice_agent_seconds", duration, "manual streaming hotkey")
            print(
                f"maya-hotkey-session-closed> reason={self.close_reason.value} "
                f"audio_errors={self.audio_error_count} output_resets={self.output_reset_count} "
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
        silence_ms = int(os.getenv("XAI_VOICE_TURN_SILENCE_MS", "700"))
        return {
            "type": "session.update",
            "session": {
                "voice": os.getenv("XAI_VOICE_AGENT_VOICE", "ara"),
                "instructions": self.instructions,
                "input_audio_transcription": {"model": os.getenv("XAI_VOICE_TRANSCRIPTION_MODEL", "grok-2-audio")},
                "turn_detection": {
                    "type": "server_vad",
                    "silence_duration_ms": silence_ms,
                    "prefix_padding_ms": 500,
                },
                "tools": voice_tools(),
                "audio": {
                    "input": {"format": {"type": "audio/pcm", "rate": self.sample_rate}},
                    "output": {"format": {"type": "audio/pcm", "rate": self.sample_rate}},
                },
            },
        }

    async def _stream_input(self) -> None:
        loop = asyncio.get_running_loop()

        def callback(indata, frames, time_info, status):
            if self.stop_event.is_set():
                return
            data = bytes(indata)
            loop.call_soon_threadsafe(put_latest, self.audio_queue, data)

        with self._open_input_stream(callback):
            while not self.stop_event.is_set():
                audio = await self.audio_queue.get()
                if self.stop_event.is_set():
                    break
                if not self.session_ready.is_set():
                    self._buffer_audio(audio)
                    continue
                await self.websocket.send(json.dumps(append_audio_message(audio)))

    def _open_input_stream(self, callback):
        refresh_sounddevice_hostapi()
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
            self.input_device = resolve_sounddevice_input()
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
