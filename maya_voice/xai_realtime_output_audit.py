from __future__ import annotations

import asyncio
import contextlib
import os

from maya_voice.voice_output_audit import audit_events_for_transcript
from maya_voice.voice_session_log import record_voice_turn


class XaiRealtimeOutputAuditMixin:
    def _init_output_audit_state(self) -> None:
        self.assistant_transcripts_by_response: dict[str, tuple[str, bool]] = {}
        self.assistant_transcript_audited_responses: set[str] = set()
        self.assistant_transcript_audit_tasks: dict[str, asyncio.Task] = {}
        self.assistant_transcript_no_response_count = 0

    def _assistant_audit_response_id(self) -> str:
        response_id = str(getattr(self, "current_response_id", "") or "")
        if response_id:
            return response_id
        self.assistant_transcript_no_response_count = int(
            getattr(self, "assistant_transcript_no_response_count", 0)
        ) + 1
        return f"no_response_{self.assistant_transcript_no_response_count}"

    def _store_assistant_transcript_for_audit(self, response_id: str, transcript: str, interrupted: bool) -> None:
        if not hasattr(self, "assistant_transcripts_by_response"):
            self._init_output_audit_state()
        self.assistant_transcripts_by_response[response_id] = (transcript, interrupted)
        self._schedule_assistant_transcript_audit(response_id)

    def _schedule_assistant_transcript_audit(self, response_id: str) -> None:
        if response_id in getattr(self, "assistant_transcript_audited_responses", set()):
            return
        tasks = getattr(self, "assistant_transcript_audit_tasks", {})
        existing = tasks.get(response_id)
        if existing and not existing.done():
            return
        task = asyncio.create_task(self._delayed_assistant_transcript_audit(response_id))
        tasks[response_id] = task
        self.assistant_transcript_audit_tasks = tasks
        task.add_done_callback(lambda _: tasks.pop(response_id, None))

    async def _delayed_assistant_transcript_audit(self, response_id: str) -> None:
        await asyncio.sleep(float(os.getenv("XAI_VOICE_TOOL_AUDIT_DELAY_SECONDS", "0.6")))
        await self._audit_assistant_transcript_for_response(response_id)

    async def _audit_assistant_transcript_for_response(self, response_id: str) -> None:
        if response_id in getattr(self, "assistant_transcript_audited_responses", set()):
            return
        stored = getattr(self, "assistant_transcripts_by_response", {}).get(response_id)
        if not stored:
            return
        transcript, _interrupted = stored
        tool_calls = set(getattr(self, "tool_calls_by_response", {}).get(response_id, set()))
        for event_type, content in audit_events_for_transcript(transcript, tool_calls):
            await record_voice_turn(
                self.db_path,
                self.voice_log_session_id,
                "system",
                content,
                event_type=event_type,
                response_id=response_id,
                diagnostics={"transcript": transcript[:800], "tool_calls": sorted(tool_calls)},
            )
        self.assistant_transcript_audited_responses.add(response_id)

    async def _flush_assistant_transcript_audits(self) -> None:
        for response_id in list(getattr(self, "assistant_transcripts_by_response", {})):
            await self._audit_assistant_transcript_for_response(response_id)
        for task in list(getattr(self, "assistant_transcript_audit_tasks", {}).values()):
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        getattr(self, "assistant_transcript_audit_tasks", {}).clear()
