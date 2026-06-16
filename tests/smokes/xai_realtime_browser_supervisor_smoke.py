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
import threading
import tempfile
import time
from pathlib import Path

import maya_voice.browser_runtime as browser_runtime
import xai_realtime_tools
from browser_extension_bridge import remember_extension_open_result
from storage import init_db
from xai_realtime_events import XaiRealtimeEventMixin
from xai_realtime_tools import BROWSER_TOOL_NAME
from maya_voice.tool_specs import voice_tools
from xai_voice_work import voice_work_status_text


class FakeWebSocket:
    def __init__(self):
        self.sent = []

    async def send(self, payload):
        self.sent.append(json.loads(payload))


class FakeRealtimeSession(XaiRealtimeEventMixin):
    def __init__(self, db_path):
        self.db_path = db_path
        self.voice_log_session_id = None
        self.current_response_id = "resp_browser"
        self.function_call_tasks = set()
        self.stop_event = asyncio.Event()
        self.websocket = FakeWebSocket()
        self.assistant = None
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


async def _call_browser_tool(session: FakeRealtimeSession, request: str):
    await session._handle_function_call(
        {
            "name": BROWSER_TOOL_NAME,
            "call_id": "call_browser",
            "arguments": json.dumps({"request": request}),
        }
    )


async def main():
    os.environ["XAI_VOICE_WORK_CONTEXT_GRACE_SECONDS"] = "0.01"
    original_browser_capability = browser_runtime.run_browser_capability
    original_preflight = xai_realtime_tools.browser_bridge_preflight_isolated
    original_status = browser_runtime.extension_bridge_status
    old_preflight_seconds = os.environ.get("MAYA_VOICE_BROWSER_PREFLIGHT_SECONDS")
    browser_tool = next(tool for tool in voice_tools() if tool["name"] == BROWSER_TOOL_NAME)
    description = browser_tool["description"]
    assert "browser operation that Maya has chosen as the intended next action" in description
    assert "not background research for ordinary conversation" in description
    assert "answer in voice or offer a lookup" in description
    assert "for 'tell me'" not in description
    assert "or 'recommend'" not in description
    os.environ.pop("MAYA_VOICE_BROWSER_PREFLIGHT_SECONDS", None)
    assert browser_runtime.browser_preflight_seconds() == 12

    try:
        calls = []
        preflight_ready = True
        first_tool_started = threading.Event()
        finish_first_tool = threading.Event()

        async def fake_browser_capability(_db_path, request):
            calls.append(request)
            remember_extension_open_result({
                "tabId": 101,
                "groupId": 202,
                "windowId": 303,
                "openedInMayaGroup": True,
                "url": "https://www.google.com/search?q=Kazakhstan",
                "title": "Kazakhstan - Google Search",
            })
            if len(calls) == 1:
                first_tool_started.set()
                finish_first_tool.wait(timeout=2)
                return "Google Search opened Kazakhstan."
            return "Browser update applied. Opened the visible Reddit result."

        async def fake_preflight(**_kwargs):
            reason = "connected" if preflight_ready else "browser_bridge_unavailable"
            return {"ready": preflight_ready, "client_connected": preflight_ready, "reason_code": reason, "server_pid": 1234}

        browser_runtime.run_browser_capability = fake_browser_capability
        xai_realtime_tools.browser_bridge_preflight_isolated = fake_preflight
        browser_runtime.extension_bridge_status = lambda: {"client_connected": True, "connected": True, "reason_code": "connected", "server_pid": 1234}

        with tempfile.TemporaryDirectory(prefix="maya-browser-no-transcript-") as tmp:
            db_path = str(Path(tmp) / "smoke.db")
            await init_db(db_path)
            session = FakeRealtimeSession(db_path)
            await session._maybe_start_supervised_browser_work("Can you Google search Kazakhstan for me?")
            await session._maybe_start_supervised_browser_work("yes please")
            assert session.function_call_tasks == set()
            assert session.websocket.sent == []
            assert not session.supervised_voice_work_id
            assert "No active Maya work" in await voice_work_status_text(db_path)

        with tempfile.TemporaryDirectory(prefix="maya-browser-tool-start-") as tmp:
            db_path = str(Path(tmp) / "smoke.db")
            await init_db(db_path)
            session = FakeRealtimeSession(db_path)

            await _call_browser_tool(session, "Can you Google search Kazakhstan for me?")
            assert await asyncio.to_thread(first_tool_started.wait, 1)
            assert session.supervised_voice_work_request == "Can you Google search Kazakhstan for me?"
            assert session.supervised_voice_work_tool_name == BROWSER_TOOL_NAME
            assert session.supervised_voice_work_kind == "browser"
            assert session.supervised_voice_work_id
            assert session.supervised_browser_request == "Can you Google search Kazakhstan for me?"
            assert not any(
                "Speak only the acknowledgement" in sent.get("item", {}).get("content", [{}])[0].get("text", "")
                for sent in session.websocket.sent
                if sent.get("type") == "conversation.item.create"
            )
            captured = await session._maybe_capture_supervised_voice_followup("Maybe the Reddit one?")
            ignored = await session._maybe_capture_supervised_voice_followup("can you hear me Maya?")
            assert captured is False
            assert ignored is False
            finish_first_tool.set()
            await asyncio.gather(*session.function_call_tasks)
            assert len(calls) == 1
            assert calls[0] == "Can you Google search Kazakhstan for me?"
            assert session.websocket.sent[-2]["item"]["type"] == "function_call_output"
            assert "done browser: Can you Google search Kazakhstan" in await voice_work_status_text(db_path)

            await _call_browser_tool(session, "Maybe the Reddit one?")
            await asyncio.gather(*session.function_call_tasks)
            assert len(calls) == 2
            assert calls[1] == "Maybe the Reddit one?"

        with tempfile.TemporaryDirectory(prefix="maya-browser-empty-tool-") as tmp:
            db_path = str(Path(tmp) / "smoke.db")
            await init_db(db_path)
            session = FakeRealtimeSession(db_path)
            await _call_browser_tool(session, "")
            await asyncio.gather(*session.function_call_tasks)
            output = session.websocket.sent[-2]["item"]["output"]
            assert "Status: needs_clarification" in output
            assert "empty_request" in output
            assert "No active Maya work" in await voice_work_status_text(db_path)

        with tempfile.TemporaryDirectory(prefix="maya-browser-preflight-fail-") as tmp:
            preflight_ready = False
            before = len(calls)
            db_path = str(Path(tmp) / "smoke.db")
            await init_db(db_path)
            output = await xai_realtime_tools.run_voice_browser_skill(db_path, "Google search Langkawi")
            assert "Status: failed" in output
            assert "browser_bridge_unavailable" in output
            assert len(calls) == before
            assert "failed browser: Google search Langkawi" in await voice_work_status_text(db_path)
            preflight_ready = True

        async def failed_browser_capability(_db_path, request):
            return "I could not inspect Chrome yet: extension op 'page_text' failed: no Maya tab open yet"

        browser_runtime.run_browser_capability = failed_browser_capability
        with tempfile.TemporaryDirectory(prefix="maya-browser-fail-") as tmp:
            db_path = str(Path(tmp) / "smoke.db")
            await init_db(db_path)
            output = await xai_realtime_tools.run_voice_browser_skill(
                db_path,
                "Open the Metacritic page for The Witcher 3",
                voice_session_id="voice-test",
            )
            assert "Status: failed" in output
            assert "Do not say the browser opened" in output
            status = await voice_work_status_text(db_path)
            assert "failed browser: Open the Metacritic page for The Witcher 3" in status

        async def hanging_browser_capability(_db_path, request):
            time.sleep(10)
            return "should not return"

        browser_runtime.run_browser_capability = hanging_browser_capability
        old_timeout = os.environ.get("XAI_VOICE_BROWSER_TOOL_TIMEOUT_SECONDS")
        os.environ["XAI_VOICE_BROWSER_TOOL_TIMEOUT_SECONDS"] = "0.01"
        try:
            with tempfile.TemporaryDirectory(prefix="maya-browser-timeout-") as tmp:
                db_path = str(Path(tmp) / "smoke.db")
                await init_db(db_path)
                output = await xai_realtime_tools.run_voice_browser_skill(db_path, "Google search Sri Lanka visa")
                assert "Status: failed" in output
                assert "browser_tool_timeout" in output
                assert "failed browser: Google search Sri Lanka visa" in await voice_work_status_text(db_path)
        finally:
            if old_timeout is None:
                os.environ.pop("XAI_VOICE_BROWSER_TOOL_TIMEOUT_SECONDS", None)
            else:
                os.environ["XAI_VOICE_BROWSER_TOOL_TIMEOUT_SECONDS"] = old_timeout
    finally:
        browser_runtime.run_browser_capability = original_browser_capability
        xai_realtime_tools.browser_bridge_preflight_isolated = original_preflight
        browser_runtime.extension_bridge_status = original_status
        if old_preflight_seconds is None:
            os.environ.pop("MAYA_VOICE_BROWSER_PREFLIGHT_SECONDS", None)
        else:
            os.environ["MAYA_VOICE_BROWSER_PREFLIGHT_SECONDS"] = old_preflight_seconds
    print("xai_realtime_browser_supervisor_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
