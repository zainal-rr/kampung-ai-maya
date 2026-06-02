from __future__ import annotations

import asyncio
import contextlib
import os
import time

import sounddevice as sd

from sounddevice_audio import output_device_snapshot, refresh_sounddevice_hostapi, resolve_first_output
from voice_session_log import record_voice_turn
from xai_realtime_models import PlaybackCommand, SessionCloseReason
from xai_realtime_stream_helpers import put_playback


class XaiRealtimePlaybackMixin:
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
            await record_voice_turn(
                self.db_path,
                self.voice_log_session_id,
                "system",
                f"Audio output error: {exc}",
                event_type="audio_output_error",
                response_id=self.current_response_id,
                diagnostics={"audio_error_count": self.audio_error_count},
            )
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
        await self._record_pending_assistant_transcript(interrupted=True)
        await record_voice_turn(
            self.db_path,
            self.voice_log_session_id,
            "system",
            "User speech started while Maya was responding; playback interrupted and response.cancel was sent.",
            event_type="input_audio_buffer.speech_started",
            response_id=self.current_response_id,
            interrupted=True,
        )
        await self._clear_playback_queue()
        await put_playback(self.playback_queue, PlaybackCommand("interrupt"))
        self.response_active = False
        if self.websocket and was_active:
            await self.websocket.send(json.dumps({"type": "response.cancel"}))

    async def _record_pending_assistant_transcript(self, interrupted: bool) -> None:
        if not self.assistant_transcript_parts:
            return
        await self._record_assistant_transcript("".join(self.assistant_transcript_parts), interrupted=interrupted)

    async def _record_assistant_transcript(self, transcript: str, interrupted: bool) -> None:
        if self.assistant_transcript_recorded:
            return
        cleaned = transcript.strip()
        if not cleaned:
            return
        await record_voice_turn(
            self.db_path,
            self.voice_log_session_id,
            "maya",
            cleaned,
            event_type="response.output_audio_transcript",
            response_id=self.current_response_id,
            interrupted=interrupted,
        )
        self.assistant_transcript_recorded = True
        self.assistant_transcript_parts = []

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
