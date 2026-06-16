# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys

import asyncio
import json
import os
import tempfile
from pathlib import Path

from artifact_file_state import record_artifact_fingerprint
from artifact_sessions import record_artifact_session
from storage import init_db
from voice_session_log import voice_session_turns
from xai_realtime_events import XaiRealtimeEventMixin
from xai_realtime_playback import XaiRealtimePlaybackMixin
from xai_realtime_tools import CANCEL_WORK_TOOL_NAME, MAYA_WORK_TOOL_NAME, REVISE_WORK_TOOL_NAME, execute_voice_tool
from xai_voice_state_tools import read_maya_state
from xai_voice_work import (
    complete_voice_work,
    create_voice_work,
    get_voice_work,
    set_voice_work_phase,
    voice_work_status_text,
)
from maya_voice.tool_guard import empty_request_reason


class FakeWebSocket:
    def __init__(self):
        self.sent = []

    async def send(self, payload):
        self.sent.append(json.loads(payload))


class FakeAssistant:
    def __init__(self, db_path="", workspace=None, delay_event=None, fail=False):
        self.handled = []
        self.db_path = db_path
        self.workspace = Path(workspace) if workspace else None
        self.delay_event = delay_event
        self.fail = fail
        self.commands = type("FakeCommands", (), {})()
        self.commands.last_lane = ""
        self.commands.documents = type("FakeDocuments", (), {})()
        self.commands.documents.last_model_lane = ""

    async def handle_text(self, text, channel, speak_reply=False):
        self.handled.append((text, channel, speak_reply))
        if self.fail:
            raise TimeoutError("model timed out")
        self.commands.last_lane = ""
        self.commands.documents.last_model_lane = ""
        if self.delay_event is not None and len(self.handled) == 1:
            await self.delay_event.wait()
        if text == "make me a document about KL":
            self.commands.last_lane = "clarification"
            self.commands.documents.last_model_lane = "clarification"
            return "I understand: KL. Which type should I create: Word doc, Excel sheet, or PowerPoint slides?"
        if self.db_path and self.workspace and text.lower().startswith("make me a word document"):
            path = self.workspace / "meraki-mx-v1.docx"
            path.write_bytes(b"fake docx content")
            await record_artifact_session(self.db_path, channel, "docx", path, "Meraki MX brief")
            await record_artifact_fingerprint(self.db_path, path)
            return f"Created the Word document at {path}."
        if self.db_path and self.workspace and text.lower().startswith("create a word document about"):
            path = self.workspace / "kl-trip-v1.docx"
            path.write_bytes(b"fake docx content")
            await record_artifact_session(self.db_path, channel, "docx", path, "KL trip")
            await record_artifact_fingerprint(self.db_path, path)
            return f"Created the Word document at {path}."
        return "Done. I updated the latest document at /Users/zainalabidinjamal/Desktop/Maya/documents/meraki-mx-v1.docx."


class FakeRealtimeSession(XaiRealtimeEventMixin, XaiRealtimePlaybackMixin):
    def __init__(self, db_path, assistant=None):
        self.db_path = db_path
        self.voice_log_session_id = 42
        self.current_response_id = "resp_work"
        self.assistant_transcript_parts = []
        self.assistant_transcript_recorded = False
        self.tool_calls_by_response = {}
        self.function_call_tasks = set()
        self.stop_event = asyncio.Event()
        self.websocket = FakeWebSocket()
        self.assistant = assistant or FakeAssistant()
        self.response_active = True
        self.playback_queue = asyncio.Queue()
        self.drop_audio_until_next_response = False
        self.supervised_voice_work_request = ""
        self.supervised_voice_work_tool_name = ""
        self.supervised_voice_work_kind = ""
        self.supervised_voice_work_ack = ""
        self.supervised_voice_work_id = ""
        self.supervised_voice_work_followups = []
        self.supervised_voice_work_steer_events = []
        self.supervised_voice_work_applied_followup_count = 0
        self.supervised_voice_work_execution_started = False
        self.supervised_voice_work_suppress_until = 0.0
        self.supervised_voice_work_auto_cancel_until = 0.0
        self.supervised_voice_work_auto_cancelled = False
        self.supervised_voice_work_ack_pending = False
        self.supervised_voice_work_task = None
        self.supervised_browser_request = ""
        self.supervised_browser_suppress_until = 0.0
        self.supervised_browser_task = None
        self.fragment_response_text = ""
        self.fragment_response_suppression_until = 0.0

    async def _clear_playback_queue(self):
        while not self.playback_queue.empty():
            self.playback_queue.get_nowait()
            self.playback_queue.task_done()


async def _call_tool(session: FakeRealtimeSession, request: str, **extra):
    args = {"request": request}
    args.update(extra)
    await session._handle_function_call(
        {
            "name": MAYA_WORK_TOOL_NAME,
            "call_id": "call_work",
            "arguments": json.dumps(args),
        }
    )


async def main():
    os.environ["XAI_VOICE_DOCUMENT_CONTEXT_GRACE_SECONDS"] = "0.05"
    os.environ["XAI_VOICE_WORK_CONTEXT_GRACE_SECONDS"] = "0.01"

    assert empty_request_reason(False) == "empty_request"
    assert empty_request_reason(True) == ""

    with tempfile.TemporaryDirectory(prefix="maya-work-no-transcript-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        assistant = FakeAssistant(db_path, tmp)
        session = FakeRealtimeSession(db_path, assistant)

        await session._maybe_start_supervised_voice_work("Can you make me a")
        await session._maybe_start_supervised_voice_work("I told you to make me a router config")
        assert assistant.handled == []
        assert session.function_call_tasks == set()
        assert not session.supervised_voice_work_id
        assert session.websocket.sent == []
        assert "No active Maya work" in await voice_work_status_text(db_path)

    with tempfile.TemporaryDirectory(prefix="maya-work-tool-start-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        assistant = FakeAssistant(db_path, tmp)
        session = FakeRealtimeSession(db_path, assistant)

        await _call_tool(session, "make me a Meraki firewall config")
        assert session.supervised_voice_work_request == "make me a Meraki firewall config"
        assert session.supervised_voice_work_tool_name == MAYA_WORK_TOOL_NAME
        assert session.supervised_voice_work_id
        assert not any(
            sent.get("item", {}).get("content", [{}])[0].get("text", "").startswith("Speak only the acknowledgement")
            for sent in session.websocket.sent
            if sent.get("type") == "conversation.item.create"
        )
        await asyncio.gather(*session.function_call_tasks)
        assert assistant.handled == [("make me a Meraki firewall config", "imac", False)]
        assert session.websocket.sent[-2]["item"]["type"] == "function_call_output"
        assert session.websocket.sent[-1] == {"type": "response.create"}
        assert "done work: make me a Meraki firewall config" in await voice_work_status_text(db_path)

    with tempfile.TemporaryDirectory(prefix="maya-work-empty-tool-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        assistant = FakeAssistant(db_path, tmp)
        output = await execute_voice_tool(
            db_path,
            MAYA_WORK_TOOL_NAME,
            {"request": ""},
            assistant=assistant,
            voice_session_id="smoke",
        )
        assert "Status: needs_clarification" in output
        assert "empty_request" in output
        assert assistant.handled == []
        assert "No active Maya work" in await voice_work_status_text(db_path)

    with tempfile.TemporaryDirectory(prefix="maya-work-promise-audit-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        session = FakeRealtimeSession(db_path, FakeAssistant(db_path, tmp))
        session.current_response_id = "resp_no_tool"
        await session._record_assistant_transcript("I'll create that Excel now.", interrupted=False)
        turns = await voice_session_turns(db_path, session.voice_log_session_id)
        assert any(turn["event_type"] == "voice_action_promise_without_tool" for turn in turns)

    for request in ("can you make me a", "asdfqwer", "build a site readiness brief for tomorrow"):
        with tempfile.TemporaryDirectory(prefix="maya-work-tool-seam-") as tmp:
            db_path = str(Path(tmp) / "smoke.db")
            await init_db(db_path)
            assistant = FakeAssistant(db_path, tmp)
            output = await execute_voice_tool(
                db_path,
                MAYA_WORK_TOOL_NAME,
                {"request": request},
                assistant=assistant,
                voice_session_id="smoke",
            )
            assert "Status: completed" in output
            assert assistant.handled == [(request, "imac", False)]

    with tempfile.TemporaryDirectory(prefix="maya-work-tool-seam-function-call-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        assistant = FakeAssistant(db_path, tmp)
        output = await execute_voice_tool(
            db_path,
            MAYA_WORK_TOOL_NAME,
            {"request": "can you make me a"},
            assistant=assistant,
            voice_session_id="smoke",
        )
        assert "Status: completed" in output
        assert assistant.handled == [("can you make me a", "imac", False)]

    with tempfile.TemporaryDirectory(prefix="maya-work-clarification-status-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        assistant = FakeAssistant(db_path, tmp)
        output = await execute_voice_tool(
            db_path,
            MAYA_WORK_TOOL_NAME,
            {"request": "make me a document about KL"},
            assistant=assistant,
            voice_session_id="smoke",
        )
        assert "Status: needs_clarification" in output
        assert "Word doc, Excel sheet, or PowerPoint slides" in output
        assert assistant.handled == [("make me a document about KL", "imac", False)]

    with tempfile.TemporaryDirectory(prefix="maya-work-structured-artifact-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        assistant = FakeAssistant(db_path, tmp)
        output = await execute_voice_tool(
            db_path,
            MAYA_WORK_TOOL_NAME,
            {
                "request": "Create a three-day KL shopping and sightseeing travel plan for someone driving from Selangor",
                "artifact_type": "word_document",
            },
            assistant=assistant,
            voice_session_id="smoke",
        )
        assert "Status: completed" in output
        assert assistant.handled == [
            (
                "Create a Word document about Create a three-day KL shopping and sightseeing travel plan for someone driving from Selangor",
                "imac",
                False,
            )
        ]

    with tempfile.TemporaryDirectory(prefix="maya-work-steer-tool-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        finish_first = asyncio.Event()
        assistant = FakeAssistant(db_path, tmp, finish_first)
        session = FakeRealtimeSession(db_path, assistant)

        await _call_tool(
            session,
            "make me a Word document about branch firewall setup for the operations team",
            artifact_type="word_document",
        )
        revise_output = await execute_voice_tool(
            db_path,
            REVISE_WORK_TOOL_NAME,
            {"instruction": "also add an executive summary"},
            assistant=assistant,
            voice_session_id=str(session.voice_log_session_id),
        )
        assert "Status: completed" in revise_output
        assert "Revision captured" in revise_output
        finish_first.set()
        await asyncio.gather(*session.function_call_tasks)
        assert len(assistant.handled) == 1
        assert "make me a Word document about branch firewall setup for the operations team" in assistant.handled[0][0]
        assert "also add an executive summary" in assistant.handled[0][0]
        assert "Additional context" in assistant.handled[0][0]
        status = await voice_work_status_text(db_path)
        assert "Recent artifact steering" in status
        assert "applied" in status and "also add an executive summary" in status
        assert "done document: make me a Word document" in await read_maya_state(db_path, "what are you doing")

    with tempfile.TemporaryDirectory(prefix="maya-work-ambiguous-active-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        first = await create_voice_work(db_path, "make a Word doc", kind="document", voice_session_id="same")
        second = await create_voice_work(db_path, "make an Excel file", kind="document", voice_session_id="same")
        await set_voice_work_phase(db_path, first, "drafting")
        await set_voice_work_phase(db_path, second, "building")
        output = await execute_voice_tool(
            db_path,
            REVISE_WORK_TOOL_NAME,
            {"instruction": "add an executive summary"},
            assistant=FakeAssistant(db_path, tmp),
            voice_session_id="same",
        )
        assert "Status: needs_clarification" in output
        assert "More than one Maya work item is active" in output

    for phase in ("queued", "drafting", "building", "qa"):
        with tempfile.TemporaryDirectory(prefix=f"maya-work-cancel-{phase}-") as tmp:
            db_path = str(Path(tmp) / "smoke.db")
            await init_db(db_path)
            work_id = await create_voice_work(db_path, "make a Word doc", kind="document", voice_session_id="cancel")
            await set_voice_work_phase(db_path, work_id, phase)
            output = await execute_voice_tool(
                db_path,
                CANCEL_WORK_TOOL_NAME,
                {"reason": "stop that"},
                voice_session_id="cancel",
            )
            assert "Status: cancel_requested" in output
            assert await set_voice_work_phase(db_path, work_id, "opening") is False
            row = await get_voice_work(db_path, work_id)
            assert row["phase"] == "cancelled"

    with tempfile.TemporaryDirectory(prefix="maya-work-cancel-completed-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        work_id = await create_voice_work(db_path, "make a Word doc", kind="document", voice_session_id="done")
        await complete_voice_work(db_path, work_id, result="done", status="completed")
        output = await execute_voice_tool(
            db_path,
            CANCEL_WORK_TOOL_NAME,
            {"work_id": work_id, "reason": "never mind"},
            voice_session_id="done",
        )
        assert "Status: already_completed" in output

    with tempfile.TemporaryDirectory(prefix="maya-work-failure-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        assistant = FakeAssistant(db_path, tmp, fail=True)
        output = await execute_voice_tool(
            db_path,
            MAYA_WORK_TOOL_NAME,
            {"request": "make a Word document"},
            assistant=assistant,
            voice_session_id="fail",
        )
        assert "Status: failed" in output
        assert "model timed out" in output

    assert not Path("maya_voice/readiness.py").exists()
    realtime_sources = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in ("xai_realtime_tools.py", "xai_realtime_voice_work.py", "xai_realtime_events.py")
    )
    assert "maya_voice.readiness" not in realtime_sources
    assert "evaluate_voice_work_readiness" not in realtime_sources

    print("xai_realtime_work_supervisor_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
