from __future__ import annotations

import asyncio
import contextlib
import json
import time

from voice_session_log import record_voice_turn
from xai_realtime_tools import BROWSER_TOOL_NAME, MAYA_WORK_TOOL_NAME
from xai_voice_supervisor import SupervisedVoiceWork, classify_supervised_voice_work


class XaiRealtimeVoiceWorkMixin:
    async def _maybe_start_supervised_voice_work(self, transcript: str) -> None:
        work = _supervised_voice_work(transcript)
        if work is None or self._voice_work_supervisor_is_active():
            return
        self.supervised_voice_work_request = work.request
        self.supervised_voice_work_tool_name = work.tool_name
        self.supervised_voice_work_kind = work.kind
        self.supervised_voice_work_ack = work.acknowledgement
        self.supervised_voice_work_suppress_until = time.monotonic() + 120.0
        self.supervised_voice_work_ack_pending = True
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
            diagnostics={"request": work.request, "kind": work.kind, "tool": work.tool_name},
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

    async def _cancel_auto_response_for_supervised_voice_work(self) -> bool:
        if not self._voice_work_supervisor_is_active():
            return False
        if getattr(self, "supervised_voice_work_ack_pending", False):
            self.supervised_voice_work_ack_pending = False
            return False
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
            output = await event_module.execute_voice_tool(
                self.db_path,
                work.tool_name,
                {"request": work.request},
                assistant=getattr(self, "assistant", None),
                voice_session_id=str(self.voice_log_session_id or ""),
                short_ack=work.acknowledgement,
                work_kind=work.kind,
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

    async def _run_supervised_browser_work(self, request: str) -> None:
        work = SupervisedVoiceWork(request=request, kind="browser", tool_name=BROWSER_TOOL_NAME, acknowledgement="Okay, I’m opening that now.")
        await self._run_supervised_voice_work(work)

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
        return bool(has_request and time.monotonic() < getattr(self, "supervised_voice_work_suppress_until", 0.0) and task is not None and not task.done())

    def _supervisor_owns_tool(self, name: str) -> bool:
        return self._voice_work_supervisor_is_active() and name in {BROWSER_TOOL_NAME, MAYA_WORK_TOOL_NAME} and name == getattr(self, "supervised_voice_work_tool_name", "")

    def _clear_supervised_voice_work(self) -> None:
        self.supervised_voice_work_request = ""
        self.supervised_voice_work_tool_name = ""
        self.supervised_voice_work_kind = ""
        self.supervised_voice_work_ack = ""
        self.supervised_voice_work_suppress_until = 0.0
        self.supervised_voice_work_ack_pending = False
        self.supervised_browser_request = ""
        self.supervised_browser_suppress_until = 0.0


def _supervised_browser_request(transcript: str) -> str:
    work = _supervised_voice_work(transcript)
    return work.request if work and work.tool_name == BROWSER_TOOL_NAME else ""


def _supervised_voice_work(transcript: str) -> SupervisedVoiceWork | None:
    return classify_supervised_voice_work(transcript, browser_tool_name=BROWSER_TOOL_NAME, work_tool_name=MAYA_WORK_TOOL_NAME)


def _looks_like_browser_status_question(lowered: str) -> bool:
    return any(marker in lowered for marker in ("what are you doing", "what did you do", "what happened", "show the request", "pull up the request", "status", "how will you search", "who will be doing"))
