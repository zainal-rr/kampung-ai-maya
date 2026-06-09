from __future__ import annotations

import asyncio
import json
import time

from voice_session_log import record_voice_turn
from xai_realtime_models import PlaybackCommand, SessionCloseReason, _decode_audio_delta
from xai_realtime_stream_helpers import append_audio_message, event_error, put_playback
from xai_realtime_tools import BROWSER_TOOL_NAME, MAYA_WORK_TOOL_NAME, execute_voice_tool
from xai_realtime_vad_guard import XaiRealtimeVadGuardMixin
from xai_realtime_voice_work import (
    XaiRealtimeVoiceWorkMixin,
    _looks_like_browser_status_question,
    _supervised_browser_request,
    _supervised_voice_work,
)


class XaiRealtimeEventMixin(XaiRealtimeVoiceWorkMixin, XaiRealtimeVadGuardMixin):
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
                await self._record_pending_assistant_transcript(interrupted=False)
                response = event.get("response") or {}
                self.current_response_id = response.get("id", "")
                self.assistant_transcript_parts = []
                self.assistant_transcript_recorded = False
                self.response_active = True
                self.drop_audio_until_next_response = False
                self.underrun_logged_for_response = False
                self.vad_silent_logged_for_response = False
                self.peak_local_mic_rms_since_response = 0.0
                self.peak_local_mic_rms_since_response_at = 0.0
                if await self._cancel_auto_response_for_supervised_voice_work():
                    continue
                if await self._cancel_incomplete_fragment_response():
                    continue
            elif event_type == "input_audio_buffer.speech_started":
                self._touch_activity()
                self.last_xai_speech_started_at = time.monotonic()
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
                delta = event.get("delta", "")
                print(delta, end="", flush=True)
                if delta:
                    self.assistant_transcript_parts.append(delta)
            elif event_type == "response.output_audio_transcript.done":
                self._touch_activity()
                transcript = event.get("transcript", "") or "".join(self.assistant_transcript_parts)
                await self._record_assistant_transcript(transcript, interrupted=False)
            elif event_type == "response.output_audio.done":
                self._touch_activity()
                self.last_response_done_at = time.monotonic()
                self.response_active = False
                self.drop_audio_until_next_response = False
                await put_playback(self.playback_queue, PlaybackCommand("end_response"))
            elif event_type == "response.done":
                self._touch_activity()
                self.last_response_done_at = time.monotonic()
                await self._record_pending_assistant_transcript(interrupted=False)
                await put_playback(self.playback_queue, PlaybackCommand("end_response"))
                self.response_active = False
                self.drop_audio_until_next_response = False
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
                self.last_user_transcript_at = time.monotonic()
                transcript = event.get("transcript", "")
                print(f"\nmaya-hotkey-heard> {transcript}", flush=True)
                if transcript:
                    self._update_fragment_response_guard(transcript)
                    self.transcripts.append(transcript)
                    await record_voice_turn(
                        self.db_path,
                        self.voice_log_session_id,
                        "user",
                        transcript,
                        event_type=event_type,
                    )
                    await self._maybe_start_supervised_voice_work(transcript)

    async def _handle_function_call(self, event: dict) -> None:
        name = event.get("name", "")
        call_id = event.get("call_id")
        if not name or not call_id:
            return
        if self._supervisor_owns_tool(name):
            print(f"maya-hotkey-tool-note> ignored duplicate {name}; voice supervisor already started it", flush=True)
            return
        print(f"maya-hotkey-tool> {name}", flush=True)
        try:
            args = json.loads(event.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}
        await record_voice_turn(
            self.db_path,
            self.voice_log_session_id,
            "tool",
            f"call {name} args {json.dumps(args, ensure_ascii=True)[:1200]}",
            event_type="response.function_call_arguments.done",
            response_id=self.current_response_id,
            tool_name=name,
        )
        task = asyncio.create_task(
            self._run_function_call_task(
                name=name,
                args=args,
                call_id=call_id,
                response_id=self.current_response_id,
            )
        )
        self.function_call_tasks.add(task)
        task.add_done_callback(self.function_call_tasks.discard)

    async def _run_function_call_task(self, *, name: str, args: dict, call_id: str, response_id: str) -> None:
        try:
            output = await execute_voice_tool(
                self.db_path,
                name,
                args,
                assistant=getattr(self, "assistant", None),
                voice_session_id=str(self.voice_log_session_id or ""),
            )
        except Exception as exc:
            output = (
                "I could not finish that request. "
                f"Reason: {exc}"
            )
            print(f"maya-hotkey-tool-error> {name}: {exc}", flush=True)
        await record_voice_turn(
            self.db_path,
            self.voice_log_session_id,
            "tool",
            f"result {output[:1600]}",
            event_type="function_call_output",
            response_id=response_id,
            tool_name=name,
        )
        if self.stop_event.is_set():
            return
        if not self.websocket:
            return
        try:
            await self.websocket.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": output,
                },
            }))
            await self.websocket.send(json.dumps({"type": "response.create"}))
        except Exception as exc:
            print(f"maya-hotkey-tool-note> result saved but voice session could not receive it: {exc}", flush=True)

    async def _flush_pending_audio(self) -> None:
        for audio in self.pending_audio:
            self._mark_input_sent(audio)
            await self.websocket.send(json.dumps(append_audio_message(audio)))
        self.pending_audio.clear()

    def _buffer_audio(self, audio: bytes) -> None:
        self.pending_audio.append(audio)
        if len(self.pending_audio) > self.max_pending_chunks:
            self.pending_audio.pop(0)
