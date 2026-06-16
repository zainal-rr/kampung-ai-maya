from __future__ import annotations

import asyncio
import json
import time

from voice_session_log import record_voice_turn
from xai_realtime_models import PlaybackCommand, SessionCloseReason, _decode_audio_delta
from xai_realtime_stream_helpers import append_audio_message, event_error, put_playback
from artifact_steering import pending_steer_events_for_work, update_artifact_steer_event
from maya_voice.tool_results import failed_tool_result_for_maya, tool_result_for_maya
from xai_realtime_tools import BROWSER_TOOL_NAME, MAYA_WORK_TOOL_NAME, execute_voice_tool
from xai_realtime_vad_guard import XaiRealtimeVadGuardMixin
from xai_realtime_voice_work import (
    XaiRealtimeVoiceWorkMixin,
)
from xai_voice_supervisor import SupervisedVoiceWork
from xai_voice_work import complete_voice_work, set_voice_work_phase, voice_work_cancel_requested
from xai_voice_work_followups import context_grace_seconds


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
        print(f"maya-hotkey-tool> {name}", flush=True)
        if self.current_response_id:
            calls = getattr(self, "tool_calls_by_response", {})
            calls.setdefault(self.current_response_id, set()).add(name)
            self.tool_calls_by_response = calls
        try:
            args = json.loads(event.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}
        if self._supervisor_owns_tool(name, args):
            print(f"maya-hotkey-tool-note> ignored duplicate {name}; voice supervisor already started it", flush=True)
            return
        supervised = await self._begin_supervised_tool_call(name, args)
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
                work_kind=str(supervised.get("kind") or ""),
                voice_work_id=str(supervised.get("work_id") or "") or None,
                supervised_request=str(supervised.get("request") or ""),
            )
        )
        self._attach_supervised_tool_task(task, name, str(supervised.get("work_id") or "") or None)
        self.function_call_tasks.add(task)
        task.add_done_callback(self.function_call_tasks.discard)

    async def _run_function_call_task(
        self,
        *,
        name: str,
        args: dict,
        call_id: str,
        response_id: str,
        work_kind: str = "",
        voice_work_id: str | None = None,
        supervised_request: str = "",
    ) -> None:
        try:
            if voice_work_id and name in {BROWSER_TOOL_NAME, MAYA_WORK_TOOL_NAME}:
                args = await self._prepare_supervised_tool_args(
                    name=name,
                    args=args,
                    work_kind=work_kind,
                    voice_work_id=voice_work_id,
                    supervised_request=supervised_request,
                )
                if await voice_work_cancel_requested(self.db_path, voice_work_id):
                    output = tool_result_for_maya(
                        supervised_request or str(args.get("request") or ""),
                        "I cancelled that work before opening or delivering anything.",
                        status="cancelled",
                    )
                    await complete_voice_work(
                        self.db_path,
                        voice_work_id,
                        result=output,
                        status="cancelled",
                    )
                    await self._send_function_call_output(call_id, response_id, name, output)
                    return
            output = await execute_voice_tool(
                self.db_path,
                name,
                args,
                assistant=getattr(self, "assistant", None),
                voice_session_id=str(self.voice_log_session_id or ""),
                work_kind=work_kind,
                voice_work_id=voice_work_id,
            )
            if voice_work_id and name in {BROWSER_TOOL_NAME, MAYA_WORK_TOOL_NAME}:
                work = SupervisedVoiceWork(
                    request=supervised_request or str(args.get("request") or args.get("question") or args.get("text") or ""),
                    kind=work_kind or "work",
                    tool_name=name,
                    acknowledgement="",
                )
                output = await self._apply_late_supervised_followups(
                    __import__("xai_realtime_events"),
                    work,
                    output,
                    getattr(self, "supervised_voice_work_applied_followup_count", 0),
                )
        except Exception as exc:
            output = failed_tool_result_for_maya(
                str(args.get("request") or args.get("question") or args.get("text") or name),
                exc,
                work_id=voice_work_id,
            )
            if voice_work_id and name in {BROWSER_TOOL_NAME, MAYA_WORK_TOOL_NAME}:
                await set_voice_work_phase(self.db_path, voice_work_id, "failed", str(exc))
                await complete_voice_work(self.db_path, voice_work_id, result=output, status="failed")
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
        await self._send_function_call_output(call_id, response_id, name, output)
        if voice_work_id and name in {BROWSER_TOOL_NAME, MAYA_WORK_TOOL_NAME}:
            self._clear_supervised_voice_work()

    async def _prepare_supervised_tool_args(
        self,
        *,
        name: str,
        args: dict,
        work_kind: str,
        voice_work_id: str,
        supervised_request: str,
    ) -> dict:
        await asyncio.sleep(context_grace_seconds(work_kind or "work"))
        if name != MAYA_WORK_TOOL_NAME:
            return args
        request = supervised_request or str(args.get("request") or args.get("question") or args.get("text") or "")
        followups = [item for item in getattr(self, "supervised_voice_work_followups", []) if str(item).strip()]
        steer_events = getattr(self, "supervised_voice_work_steer_events", [])
        pending_events = await pending_steer_events_for_work(self.db_path, voice_work_id)
        for event in pending_events:
            text = str(event.get("steer_text") or "").strip()
            if text and text not in followups:
                followups.append(text)
                steer_events.append({"id": str(event.get("id") or ""), "text": text})
        self.supervised_voice_work_followups = followups
        self.supervised_voice_work_steer_events = steer_events
        self.supervised_voice_work_applied_followup_count = len(followups)
        if followups:
            args = dict(args)
            args["request"] = _request_with_opaque_revisions(request, followups)
            for event in steer_events[: len(followups)]:
                await update_artifact_steer_event(
                    self.db_path,
                    str(event.get("id") or ""),
                    status="applied",
                    action_taken="merged_initial_request",
                )
        return args

    async def _send_function_call_output(self, call_id: str, response_id: str, name: str, output: str) -> None:
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


def _request_with_opaque_revisions(request: str, revisions: list[str]) -> str:
    clean_revisions = [" ".join(str(item).strip().split()) for item in revisions if str(item).strip()]
    if not clean_revisions:
        return request
    lines = [request.strip(), "", "Additional context from explicit revise_maya_work tool calls:"]
    lines.extend(f"- {item}" for item in clean_revisions)
    return "\n".join(lines).strip()
