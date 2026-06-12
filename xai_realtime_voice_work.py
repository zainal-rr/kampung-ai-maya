from __future__ import annotations

import asyncio
import contextlib
import json
import time

from voice_session_log import record_voice_turn
from artifact_steering import (
    apply_late_artifact_steers,
    create_artifact_steer_event,
    update_artifact_steer_event,
)
from xai_realtime_tools import BROWSER_TOOL_NAME, MAYA_WORK_TOOL_NAME
from xai_voice_work_followups import (
    artifact_type_for_request,
    auto_cancel_seconds,
    context_grace_seconds,
    extract_followup_context,
    looks_like_browser_status_question as _looks_like_browser_status_question,
    looks_like_work_followup,
    request_with_followups,
    supervised_browser_request as _supervised_browser_request,
    supervised_voice_work as _supervised_voice_work,
)
from xai_voice_work import create_voice_work
from xai_voice_supervisor import SupervisedVoiceWork


class XaiRealtimeVoiceWorkMixin:
    async def _maybe_start_supervised_voice_work(self, transcript: str) -> None:
        work = _supervised_voice_work(transcript)
        if self._voice_work_supervisor_is_active():
            await self._maybe_capture_supervised_voice_followup(transcript)
            return
        if work is None:
            return
        self.supervised_voice_work_request = work.request
        self.supervised_voice_work_tool_name = work.tool_name
        self.supervised_voice_work_kind = work.kind
        self.supervised_voice_work_ack = work.acknowledgement
        self.supervised_voice_work_followups = []
        self.supervised_voice_work_steer_events = []
        self.supervised_voice_work_applied_followup_count = 0
        self.supervised_voice_work_execution_started = False
        self.supervised_voice_work_suppress_until = time.monotonic() + 120.0
        self.supervised_voice_work_auto_cancel_until = time.monotonic() + auto_cancel_seconds()
        self.supervised_voice_work_auto_cancelled = False
        self.supervised_voice_work_ack_pending = True
        self.supervised_voice_work_id = await create_voice_work(
            self.db_path,
            work.request,
            kind=work.kind,
            voice_session_id=str(self.voice_log_session_id or ""),
            short_ack=work.acknowledgement,
        ) or ""
        if work.tool_name == BROWSER_TOOL_NAME:
            self.supervised_browser_request = work.request
            self.supervised_browser_suppress_until = self.supervised_voice_work_suppress_until
        self.drop_audio_until_next_response = True
        await self._clear_playback_queue()
        await record_voice_turn(
            self.db_path,
            self.voice_log_session_id,
            "system",
            f"Supervised voice work started from transcript: {work.request}",
            event_type="supervised_voice_work.started",
            diagnostics={
                "request": work.request,
                "kind": work.kind,
                "tool": work.tool_name,
                "work_id": self.supervised_voice_work_id,
            },
        )
        if self.websocket and self.response_active:
            with contextlib.suppress(Exception):
                await self.websocket.send(json.dumps({"type": "response.cancel"}))
            self.response_active = False
        await self._send_supervised_voice_ack(work)
        task = asyncio.create_task(self._run_supervised_voice_work(work))
        self.supervised_voice_work_task = task
        if work.tool_name == BROWSER_TOOL_NAME:
            self.supervised_browser_task = task
        self.function_call_tasks.add(task)
        task.add_done_callback(self.function_call_tasks.discard)

    async def _maybe_start_supervised_browser_work(self, transcript: str) -> None:
        await self._maybe_start_supervised_voice_work(transcript)

    async def _send_supervised_voice_ack(self, work: SupervisedVoiceWork) -> None:
        self.drop_audio_until_next_response = False
        if self.stop_event.is_set() or not self.websocket:
            return
        prompt = (
            "Say exactly this short acknowledgement to Zainal, then stop. "
            "Do not call tools and do not mention internal systems.\n\n"
            f"{work.acknowledgement}"
        )
        try:
            await self.websocket.send(json.dumps({
                "type": "conversation.item.create",
                "item": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": prompt}]},
            }))
            await self.websocket.send(json.dumps({"type": "response.create"}))
        except Exception as exc:
            print(f"maya-hotkey-supervisor-note> acknowledgement could not be spoken: {exc}", flush=True)

    async def _maybe_capture_supervised_voice_followup(self, transcript: str) -> bool:
        followup = extract_followup_context(transcript)
        if not followup:
            return False
        kind = getattr(self, "supervised_voice_work_kind", "") or "work"
        if not looks_like_work_followup(followup, kind):
            return False
        followups = getattr(self, "supervised_voice_work_followups", None)
        if followups is None:
            followups = []
            self.supervised_voice_work_followups = followups
        is_new = followup not in followups
        if is_new:
            followups.append(followup)
        timing = "running" if getattr(self, "supervised_voice_work_execution_started", False) else "pending"
        if is_new and kind == "document":
            steer_events = getattr(self, "supervised_voice_work_steer_events", None)
            if steer_events is None:
                steer_events = []
                self.supervised_voice_work_steer_events = steer_events
            event_id = await create_artifact_steer_event(
                self.db_path,
                work_id=getattr(self, "supervised_voice_work_id", ""),
                voice_session_id=str(self.voice_log_session_id or ""),
                artifact_type=artifact_type_for_request(getattr(self, "supervised_voice_work_request", "")),
                original_request=getattr(self, "supervised_voice_work_request", ""),
                steer_text=followup,
                timing=timing,
            )
            steer_events.append({"id": event_id, "text": followup})
        await record_voice_turn(
            self.db_path,
            self.voice_log_session_id,
            "system",
            f"Supervised voice work context {timing}: {followup}",
            event_type=f"supervised_voice_work.context_{timing}",
            diagnostics={
                "request": getattr(self, "supervised_voice_work_request", ""),
                "kind": kind,
                "context": followup,
                "work_id": getattr(self, "supervised_voice_work_id", ""),
            },
        )
        print(f"maya-hotkey-supervisor> captured {timing} work context: {followup}", flush=True)
        return True

    async def _cancel_auto_response_for_supervised_voice_work(self) -> bool:
        if not self._voice_work_supervisor_is_active():
            return False
        if getattr(self, "supervised_voice_work_ack_pending", False):
            self.supervised_voice_work_ack_pending = False
            return False
        if (
            getattr(self, "supervised_voice_work_auto_cancelled", False)
            or time.monotonic() > getattr(self, "supervised_voice_work_auto_cancel_until", 0.0)
        ):
            return False
        self.supervised_voice_work_auto_cancelled = True
        self.drop_audio_until_next_response = True
        await self._clear_playback_queue()
        if self.websocket:
            with contextlib.suppress(Exception):
                await self.websocket.send(json.dumps({"type": "response.cancel"}))
        self.response_active = False
        print("maya-hotkey-supervisor> cancelled pre-tool response", flush=True)
        return True

    async def _cancel_auto_response_for_supervised_browser(self) -> bool:
        return await self._cancel_auto_response_for_supervised_voice_work()

    async def _run_supervised_voice_work(self, work: SupervisedVoiceWork) -> None:
        import xai_realtime_events as event_module

        try:
            await asyncio.sleep(context_grace_seconds(work.kind))
            pending_followup_count = len(getattr(self, "supervised_voice_work_followups", []))
            work = self._work_with_captured_followups(work)
            await self._mark_initial_steers_merged(pending_followup_count)
            self.supervised_voice_work_applied_followup_count = pending_followup_count
            self.supervised_voice_work_execution_started = True
            output = await event_module.execute_voice_tool(
                self.db_path,
                work.tool_name,
                {"request": work.request},
                assistant=getattr(self, "assistant", None),
                voice_session_id=str(self.voice_log_session_id or ""),
                short_ack=work.acknowledgement,
                work_kind=work.kind,
                voice_work_id=getattr(self, "supervised_voice_work_id", "") or None,
            )
            late_followups = getattr(self, "supervised_voice_work_followups", [])[pending_followup_count:]
            late_event_ids = [
                str(item.get("id") or "")
                for item in getattr(self, "supervised_voice_work_steer_events", [])[pending_followup_count:]
            ]
            if work.kind == "document" and late_followups and getattr(self, "assistant", None):
                late_output = await apply_late_artifact_steers(
                    self.db_path,
                    assistant=getattr(self, "assistant", None),
                    work_id=getattr(self, "supervised_voice_work_id", ""),
                    voice_session_id=str(self.voice_log_session_id or ""),
                    original_request=getattr(self, "supervised_voice_work_request", "") or work.request,
                    steer_texts=late_followups,
                    event_ids=late_event_ids,
                    channel="imac",
                )
                if late_output:
                    output = f"{output}\n\n{late_output}"
        except Exception as exc:
            output = f"I could not finish that request. Reason: {exc}"
            print(f"maya-hotkey-supervisor-error> {exc}", flush=True)
        await record_voice_turn(
            self.db_path,
            self.voice_log_session_id,
            "tool",
            f"supervised voice work result {output[:1600]}",
            event_type="supervised_voice_work.result",
            tool_name=work.tool_name,
        )
        self._clear_supervised_voice_work()
        if self.stop_event.is_set() or not self.websocket:
            return
        self.drop_audio_until_next_response = False
        await self._send_supervised_voice_result(output)

    async def _send_supervised_voice_result(self, output: str) -> None:
        prompt = (
            "Maya completed this action for my last spoken request. "
            "Do not call another tool for this message. Answer briefly as Maya, without internal details.\n\n"
            f"{output}"
        )
        try:
            await self.websocket.send(json.dumps({
                "type": "conversation.item.create",
                "item": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": prompt}]},
            }))
            await self.websocket.send(json.dumps({"type": "response.create"}))
        except Exception as exc:
            print(f"maya-hotkey-supervisor-note> result saved but voice session could not receive it: {exc}", flush=True)

    def _browser_supervisor_is_active(self) -> bool:
        return self._voice_work_supervisor_is_active() and getattr(self, "supervised_voice_work_tool_name", "") == BROWSER_TOOL_NAME

    def _voice_work_supervisor_is_active(self) -> bool:
        task = getattr(self, "supervised_voice_work_task", None) or getattr(self, "supervised_browser_task", None)
        has_request = bool(getattr(self, "supervised_voice_work_request", "") or getattr(self, "supervised_browser_request", ""))
        return bool(has_request and task is not None and not task.done())

    def _supervisor_owns_tool(self, name: str) -> bool:
        return self._voice_work_supervisor_is_active() and name in {BROWSER_TOOL_NAME, MAYA_WORK_TOOL_NAME} and name == getattr(self, "supervised_voice_work_tool_name", "")

    def _clear_supervised_voice_work(self) -> None:
        self.supervised_voice_work_request = ""
        self.supervised_voice_work_tool_name = ""
        self.supervised_voice_work_kind = ""
        self.supervised_voice_work_ack = ""
        self.supervised_voice_work_followups = []
        self.supervised_voice_work_steer_events = []
        self.supervised_voice_work_applied_followup_count = 0
        self.supervised_voice_work_id = ""
        self.supervised_voice_work_execution_started = False
        self.supervised_voice_work_suppress_until = 0.0
        self.supervised_voice_work_auto_cancel_until = 0.0
        self.supervised_voice_work_auto_cancelled = False
        self.supervised_voice_work_ack_pending = False
        self.supervised_browser_request = ""
        self.supervised_browser_suppress_until = 0.0

    def _work_with_captured_followups(self, work: SupervisedVoiceWork) -> SupervisedVoiceWork:
        followups = [item for item in getattr(self, "supervised_voice_work_followups", []) if item.strip()]
        if not followups:
            return work
        combined = request_with_followups(work.request, followups)
        if combined == work.request:
            return work
        return SupervisedVoiceWork(
            request=combined,
            kind=work.kind,
            tool_name=work.tool_name,
            acknowledgement=work.acknowledgement,
        )

    async def _mark_initial_steers_merged(self, count: int) -> None:
        if count <= 0:
            return
        for item in getattr(self, "supervised_voice_work_steer_events", [])[:count]:
            event_id = str(item.get("id") or "")
            await update_artifact_steer_event(
                self.db_path,
                event_id,
                status="applied",
                action_taken="merged_initial_request",
            )
