from __future__ import annotations

import asyncio
import json
import contextlib
import os
import time
from enum import Enum

import sounddevice as sd
import websockets
from dataclasses import dataclass

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
from xai_realtime_stream_helpers import append_audio_message, event_error, put_latest, put_playback
from xai_realtime_tools import execute_voice_tool, voice_tools
from xai_voice_agent import realtime_url


@dataclass(frozen=True)
class PlaybackCommand:
    type: str
    audio: bytes = b""


class SessionCloseReason(str, Enum):
    RUNNING = "running"
    MANUAL_STOP = "manual_stop"
    IDLE = "idle"
    WEBSOCKET_TIMEOUT = "websocket_timeout"
    AUDIO_ERROR = "audio_error"
    TOOL_ERROR = "tool_error"
    ERROR = "error"
    COMPLETED = "completed"


class XaiRealtimeStreamingSession:
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

    async def run(self) -> None:
        self.started_at = time.monotonic()
        await record_route(self.db_path, "voice", "Grok Voice Agent streaming", "manual hotkey", True)
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
            await save_voice_session_summary(self.db_path, self.transcripts)
            await record_usage(self.db_path, "grok_voice_agent_seconds", duration, "manual streaming hotkey")
            print(
                f"maya-hotkey-session-closed> reason={self.close_reason.value} "
                f"audio_errors={self.audio_error_count} output_resets={self.output_reset_count} "
                f"transcripts={len(self.transcripts)} duration={duration:.1f}s",
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

    async def _receive_events(self) -> None:
        async for raw in self.websocket:
            if self.stop_event.is_set():
                break
            event = json.loads(raw)
            event_type = event.get("type", "")
            if event_type == "error":
                message = event_error(event)
                if "Cancellation failed: no active response found" in message:
                    print(f"maya-hotkey-cancel-note> {message}", flush=True)
                    self.response_active = False
                    continue
                self.close_reason = SessionCloseReason.ERROR
                raise RuntimeError(message)
            if event_type == "session.updated":
                self._touch_activity()
                self.session_ready.set()
                await self._flush_pending_audio()
            elif event_type == "response.created":
                self._touch_activity()
                self.response_active = True
                self.drop_audio_until_next_response = False
                self.underrun_logged_for_response = False
            elif event_type == "input_audio_buffer.speech_started":
                self._touch_activity()
                if self._looks_like_self_interrupt():
                    print("maya-hotkey-interrupt-note> ignored likely self-interrupt during first audio", flush=True)
                    continue
                await self._interrupt_playback()
            elif event_type == "response.output_audio.delta":
                self._touch_activity()
                if not self.drop_audio_until_next_response:
                    await put_playback(self.playback_queue, PlaybackCommand("audio", _decode_audio_delta(event)))
            elif event_type == "response.output_audio_transcript.delta":
                self._touch_activity()
                print(event.get("delta", ""), end="", flush=True)
            elif event_type in {"response.done", "response.output_audio.done"}:
                self._touch_activity()
                await put_playback(self.playback_queue, PlaybackCommand("end_response"))
                self.response_active = False
            elif event_type == "response.function_call_arguments.done":
                self._touch_activity()
                if self.stop_event.is_set():
                    break
                try:
                    await self._handle_function_call(event)
                except Exception as exc:
                    self.close_reason = SessionCloseReason.TOOL_ERROR
                    print(f"maya-hotkey-tool-error> {event.get('name', '')}: {exc}", flush=True)
                    raise
            elif event_type == "conversation.item.input_audio_transcription.completed":
                self._touch_activity()
                transcript = event.get("transcript", "")
                print(f"\nmaya-hotkey-heard> {transcript}", flush=True)
                if transcript:
                    self.transcripts.append(transcript)

    async def _handle_function_call(self, event: dict) -> None:
        name = event.get("name", "")
        call_id = event.get("call_id")
        if not name or not call_id:
            return
        print(f"maya-hotkey-tool> {name}", flush=True)
        try:
            args = json.loads(event.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}
        output = await execute_voice_tool(self.db_path, name, args)
        if self.stop_event.is_set():
            return
        await self.websocket.send(json.dumps({
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": output,
            },
        }))
        await self.websocket.send(json.dumps({"type": "response.create"}))

    async def _flush_pending_audio(self) -> None:
        for audio in self.pending_audio:
            await self.websocket.send(json.dumps(append_audio_message(audio)))
        self.pending_audio.clear()

    def _buffer_audio(self, audio: bytes) -> None:
        self.pending_audio.append(audio)
        if len(self.pending_audio) > self.max_pending_chunks:
            self.pending_audio.pop(0)

    async def _idle_watchdog(self) -> None:
        while not self.stop_event.is_set():
            await asyncio.sleep(0.5)
            if not self.session_ready.is_set() or self.response_active:
                continue
            if time.monotonic() - self.last_activity_at >= self.idle_seconds:
                print(f"maya-hotkey> idle timeout after {self.idle_seconds:g}s", flush=True)
                self.close_reason = SessionCloseReason.IDLE
                await self.stop()
                break

    def _touch_activity(self) -> None:
        self.last_activity_at = time.monotonic()

    async def _play_output(self) -> None:
        output = None
        prebuffer = bytearray()
        bytes_per_second = self.sample_rate * 2
        prebuffer_bytes = max(0, int(bytes_per_second * self.playback_prebuffer_ms / 1000))
        while not self.stop_event.is_set():
            command = await self.playback_queue.get()
            if command.type == "shutdown":
                break
            if command.type == "interrupt":
                prebuffer.clear()
                if output is not None:
                    self._close_output(output, interrupted=True)
                    output = None
                continue
            if command.type != "audio" and command.type != "end_response":
                continue
            if output is not None and self.current_output is None:
                output = None
            if command.type == "end_response":
                if prebuffer:
                    output = await self._ensure_output(output)
                    if output is not None:
                        await self._write_output(output, bytes(prebuffer))
                    prebuffer.clear()
                if output is not None:
                    self._close_output(output, interrupted=False)
                    output = None
                continue
            audio = command.audio
            if prebuffer_bytes and output is None and len(prebuffer) < prebuffer_bytes:
                prebuffer.extend(audio)
                continue
            if output is None:
                output = await self._ensure_output(output)
                if output is None:
                    prebuffer.clear()
                    continue
                if prebuffer:
                    ok = await self._write_output(output, bytes(prebuffer))
                    if not ok:
                        output = await self._reopen_output_once(output)
                        if output is not None:
                            ok = await self._write_output(output, bytes(prebuffer))
                        if not ok:
                            output = None
                    prebuffer.clear()
                    if output is None:
                        continue
            ok = await self._write_output(output, audio)
            if ok:
                self._log_playback_queue_gap()
            else:
                output = await self._reopen_output_once(output)
                if output is not None and await self._write_output(output, audio):
                    self._log_playback_queue_gap()
                else:
                    output = None
        if output is not None:
            with contextlib.suppress(Exception):
                output.stop()
            with contextlib.suppress(Exception):
                output.close()
        self.current_output = None

    async def _ensure_output(self, output):
        if output is not None:
            return output
        try:
            output_route = resolve_first_output()
            self.output_device = output_route.device
            self.output_device_name = output_route.label
            self._log_output_route(output_route)
            if self.output_device is None:
                print(f"maya-hotkey-output-unavailable> configured output not found: {self.output_device_name}", flush=True)
                return None
            output = sd.RawOutputStream(
                samplerate=self.sample_rate,
                blocksize=self.blocksize,
                device=self.output_device,
                channels=1,
                dtype="int16",
            )
            output.start()
            self.current_output = output
            self.output_started_at = time.monotonic()
            print(f"maya-hotkey> output opened: {self.output_device_name}", flush=True)
            return output
        except Exception as exc:
            print(f"maya-hotkey-output-error> {exc}", flush=True)
            refresh_sounddevice_hostapi()
            return None

    def _log_output_route(self, output_route) -> None:
        if not output_route.missing_configured and not output_route.used_default_fallback:
            return
        missing = ", ".join(output_route.missing_configured)
        route = f"{missing} -> {output_route.label}"
        if route == self.last_output_route_warning:
            return
        self.last_output_route_warning = route
        if output_route.used_default_fallback:
            print(
                f"maya-hotkey-output-fallback> headphone output unavailable after PortAudio refresh: {missing}; using {output_route.label}; outputs={output_device_snapshot()}",
                flush=True,
            )
        else:
            print(
                f"maya-hotkey-output-fallback> headphone output unavailable after PortAudio refresh: {missing}; using configured fallback {output_route.label}; outputs={output_device_snapshot()}",
                flush=True,
            )

    async def _write_output(self, output, audio: bytes) -> bool:
        try:
            await asyncio.to_thread(output.write, audio)
            return True
        except Exception as exc:
            self.audio_error_count += 1
            print(f"maya-hotkey-output-error> {exc}", flush=True)
            with contextlib.suppress(Exception):
                output.abort()
            with contextlib.suppress(Exception):
                output.stop()
            with contextlib.suppress(Exception):
                output.close()
            self.current_output = None
            refresh_sounddevice_hostapi()
            return False

    async def _reopen_output_once(self, output):
        self._close_output(output, interrupted=True, log=False)
        refresh_sounddevice_hostapi()
        self.output_reset_count += 1
        reopened = await self._ensure_output(None)
        if reopened is None:
            if self.close_reason == SessionCloseReason.RUNNING:
                self.close_reason = SessionCloseReason.AUDIO_ERROR
            print("maya-hotkey-output-retry> failed", flush=True)
            return None
        print("maya-hotkey-output-retry> reopened output after audio error", flush=True)
        return reopened

    async def _interrupt_playback(self) -> None:
        was_active = self.response_active
        self.drop_audio_until_next_response = True
        await self._clear_playback_queue()
        await put_playback(self.playback_queue, PlaybackCommand("interrupt"))
        self.response_active = False
        if self.websocket and was_active:
            await self.websocket.send(json.dumps({"type": "response.cancel"}))

    async def _clear_playback_queue(self) -> None:
        while not self.playback_queue.empty():
            try:
                self.playback_queue.get_nowait()
                self.playback_queue.task_done()
            except (asyncio.QueueEmpty, ValueError):
                break

    def _log_playback_queue_gap(self) -> None:
        now = time.monotonic()
        if self.playback_queue.empty() and not self.underrun_logged_for_response and now - self.last_underrun_log > 2.0:
            self.last_underrun_log = now
            self.underrun_logged_for_response = True
            print("maya-hotkey-playback-note> playback queue briefly empty; buffering may need tuning if audio sounds choppy", flush=True)

    def _looks_like_self_interrupt(self) -> bool:
        if self.current_output is None or not self.output_started_at:
            return False
        grace_ms = float(os.getenv("XAI_VOICE_SELF_INTERRUPT_GRACE_MS", "1200"))
        return (time.monotonic() - self.output_started_at) * 1000 < grace_ms

    def _close_output(self, output, interrupted: bool = True, log: bool = True) -> None:
        self.current_output = None
        if output is None:
            return
        if interrupted:
            with contextlib.suppress(Exception):
                output.abort()
        with contextlib.suppress(Exception):
            output.stop()
        with contextlib.suppress(Exception):
            output.close()
        if log and interrupted:
            print("maya-hotkey> playback interrupted", flush=True)
        elif log:
            print("maya-hotkey> playback closed", flush=True)

def _decode_audio_delta(event: dict) -> bytes:
    import base64
    return base64.b64decode(event.get("delta", ""))
