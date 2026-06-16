from __future__ import annotations

import asyncio
import contextlib
import json
import time

from maya_voice.voice_session_log import record_voice_turn
from maya_documents.artifact_steering import apply_late_artifact_steers, update_artifact_steer_event
from maya_voice.tool_guard import empty_request_reason
from maya_voice.artifact_manifest import create_or_get_manifest
from xai_realtime_tools import BROWSER_TOOL_NAME, MAYA_WORK_TOOL_NAME
from xai_voice_work_followups import (
    context_grace_seconds,
    extract_followup_context,
    looks_like_voice_status_question,
    send_supervised_work_status,
)
from xai_voice_work import create_voice_work
from xai_voice_supervisor import SupervisedVoiceWork


class XaiRealtimeVoiceWorkMixin:
    async def _maybe_start_supervised_voice_work(self, transcript: str) -> None:
        if self._voice_work_supervisor_is_active():
            await self._maybe_capture_supervised_voice_followup(transcript)
        return

    async def _maybe_start_supervised_browser_work(self, transcript: str) -> None:
        await self._maybe_start_supervised_voice_work(transcript)

    async def _begin_supervised_tool_call(self, tool_name: str, args: dict) -> dict:
        if tool_name not in {BROWSER_TOOL_NAME, MAYA_WORK_TOOL_NAME}:
            return {}
        request = str(args.get("request") or args.get("question") or args.get("text") or "").strip()
        if empty_request_reason(bool(request)):
            return {}
        kind = self._supervised_kind_for_tool_request(tool_name, args)
        self.supervised_voice_work_request = request
        self.supervised_voice_work_tool_name = tool_name
        self.supervised_voice_work_kind = kind
        self.supervised_voice_work_ack = ""
        self.supervised_voice_work_followups = []
        self.supervised_voice_work_steer_events = []
        self.supervised_voice_work_applied_followup_count = 0
        self.supervised_voice_work_execution_started = True
        self.supervised_voice_work_suppress_until = time.monotonic() + 120.0
        self.supervised_voice_work_auto_cancel_until = 0.0
        self.supervised_voice_work_auto_cancelled = False
        self.supervised_voice_work_ack_pending = False
        self.supervised_voice_work_id = await create_voice_work(
            self.db_path,
            request,
            kind=kind,
            voice_session_id=str(self.voice_log_session_id or ""),
            short_ack="",
        ) or ""
        if tool_name == MAYA_WORK_TOOL_NAME and self.supervised_voice_work_id:
            await create_or_get_manifest(
                self.db_path,
                self.supervised_voice_work_id,
                request=request,
                args=args,
                kind=kind,
            )
        if tool_name == BROWSER_TOOL_NAME:
            self.supervised_browser_request = request
            self.supervised_browser_suppress_until = self.supervised_voice_work_suppress_until
        await record_voice_turn(
            self.db_path,
            self.voice_log_session_id,
            "system",
            f"Supervised voice work started from tool call: {request}",
            event_type="supervised_voice_work.tool_started",
            diagnostics={
                "request": request,
                "kind": kind,
                "tool": tool_name,
                "work_id": self.supervised_voice_work_id,
            },
        )
        return {"request": request, "kind": kind, "work_id": self.supervised_voice_work_id}

    def _attach_supervised_tool_task(self, task: asyncio.Task, tool_name: str, work_id: str | None) -> None:
        if not work_id:
            return
        self.supervised_voice_work_task = task
        if tool_name == BROWSER_TOOL_NAME:
            self.supervised_browser_task = task

    def _supervised_kind_for_tool_request(self, tool_name: str, args: dict) -> str:
        if tool_name == BROWSER_TOOL_NAME:
            return "browser"
        artifact_type = str(args.get("artifact_type") or "").strip().lower()
        if artifact_type and artifact_type != "auto":
            return "document"
        return str(args.get("work_kind") or args.get("kind") or "work").strip() or "work"

    async def _maybe_capture_supervised_voice_followup(self, transcript: str) -> bool:
        followup = extract_followup_context(transcript)
        if not followup:
            return False
        if looks_like_voice_status_question(followup.lower().strip()):
            return await send_supervised_work_status(self, followup)
        await record_voice_turn(
            self.db_path,
            self.voice_log_session_id,
            "system",
            f"Supervised voice work non-status utterance left to xAI tool routing: {followup}",
            event_type="supervised_voice_work.followup_left_to_xai",
            diagnostics={
                "request": getattr(self, "supervised_voice_work_request", ""),
                "kind": getattr(self, "supervised_voice_work_kind", "") or "work",
                "context": followup,
                "work_id": getattr(self, "supervised_voice_work_id", ""),
            },
        )
        return False

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
            pending_followup_count = 0
            self.supervised_voice_work_applied_followup_count = 0
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
            "Do not call another tool. Answer briefly as Maya, without internal details. "
            "Do not begin with 'Got it', 'Okay', or 'Sure'. Use a calm pace and clear sentence breaks.\n\n"
            "If the result says Status: failed, say the action failed or could not be verified. "
            "Do not claim that a browser page, file, or action succeeded unless the result explicitly says it did.\n\n"
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

    async def _apply_late_supervised_followups(self, work: SupervisedVoiceWork, output: str, start_index: int = 0) -> str:
        late_followups = getattr(self, "supervised_voice_work_followups", [])[start_index:]
        late_event_ids = [
            str(item.get("id") or "")
            for item in getattr(self, "supervised_voice_work_steer_events", [])[start_index:]
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
                return f"{output}\n\n{late_output}"
        return output

    def _voice_work_supervisor_is_active(self) -> bool:
        task = getattr(self, "supervised_voice_work_task", None) or getattr(self, "supervised_browser_task", None)
        has_request = bool(getattr(self, "supervised_voice_work_request", "") or getattr(self, "supervised_browser_request", ""))
        return bool(has_request and task is not None and not task.done())

    def _supervisor_owns_tool(self, name: str, args: dict | None = None) -> bool:
        if not (self._voice_work_supervisor_is_active() and name in {BROWSER_TOOL_NAME, MAYA_WORK_TOOL_NAME}):
            return False
        if name != getattr(self, "supervised_voice_work_tool_name", ""):
            return False
        request = str((args or {}).get("request") or (args or {}).get("question") or (args or {}).get("text") or "").strip()
        current = str(getattr(self, "supervised_voice_work_request", "") or "").strip()
        return bool(request and current and request == current)

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
        return work

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
