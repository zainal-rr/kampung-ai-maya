import asyncio
import json
import tempfile
import time
from pathlib import Path

from storage import init_db
from xai_realtime_events import XaiRealtimeEventMixin, _supervised_voice_work
from xai_realtime_models import PlaybackCommand
from xai_realtime_tools import MAYA_WORK_TOOL_NAME
from xai_voice_state_tools import read_maya_state
from xai_voice_work import voice_work_status_text


class FakeWebSocket:
    def __init__(self):
        self.sent = []

    async def send(self, payload):
        self.sent.append(json.loads(payload))


class FakeAssistant:
    def __init__(self):
        self.handled = []

    async def handle_text(self, text, channel, speak_reply=False):
        self.handled.append((text, channel, speak_reply))
        await asyncio.sleep(0.08)
        return "Created the Word document at /Users/zainalabidinjamal/Desktop/Maya/documents/kazakhstan-hiking-v1.docx."


class FakeRealtimeSession(XaiRealtimeEventMixin):
    def __init__(self, db_path, assistant=None):
        self.db_path = db_path
        self.voice_log_session_id = 42
        self.current_response_id = "resp_work"
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
        self.supervised_voice_work_suppress_until = 0.0
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


async def main():
    work = _supervised_voice_work("make me a Word document about a Kazakhstan hiking trip")
    assert work is not None
    assert work.tool_name == MAYA_WORK_TOOL_NAME
    assert work.kind == "document"
    assert "making" in work.acknowledgement
    assert _supervised_voice_work("what are you doing") is None

    with tempfile.TemporaryDirectory(prefix="maya-work-supervisor-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        session = FakeRealtimeSession(db_path)
        await session.playback_queue.put(PlaybackCommand("audio", b"old audio"))

        started = time.monotonic()
        await session._maybe_start_supervised_voice_work("make me a Word document about a Kazakhstan hiking trip")
        elapsed = time.monotonic() - started
        assert elapsed < 0.05, f"supervisor blocked for {elapsed:.3f}s"
        assert session.playback_queue.empty()
        assert session.websocket.sent[0] == {"type": "response.cancel"}
        assert session.websocket.sent[1]["type"] == "conversation.item.create"
        ack_prompt = session.websocket.sent[1]["item"]["content"][0]["text"]
        assert "Okay, I’m making that now." in ack_prompt
        assert session.websocket.sent[2] == {"type": "response.create"}

        cancelled = await session._cancel_auto_response_for_supervised_voice_work()
        assert cancelled is False
        await asyncio.sleep(0.02)
        status = await voice_work_status_text(db_path)
        assert "running document: make me a Word document" in status
        assert "Acknowledged: Okay, I’m making that now." in status
        assert "running document" in await read_maya_state(db_path, "what are you doing")

        await asyncio.gather(*session.function_call_tasks)
        assert session.assistant.handled == [
            ("make me a Word document about a Kazakhstan hiking trip", "imac", False)
        ]
        assert session.websocket.sent[-2]["type"] == "conversation.item.create"
        assert "Maya completed this action" in session.websocket.sent[-2]["item"]["content"][0]["text"]
        assert session.websocket.sent[-1] == {"type": "response.create"}
        completed = await voice_work_status_text(db_path)
        assert "completed document: make me a Word document" in completed
        assert "kazakhstan-hiking-v1.docx" in completed

    with tempfile.TemporaryDirectory(prefix="maya-work-supervisor-stop-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        session = FakeRealtimeSession(db_path)
        await session._maybe_start_supervised_voice_work("make an Excel budget for Kazakhstan")
        before = len(session.websocket.sent)
        session.stop_event.set()
        await asyncio.gather(*session.function_call_tasks)
        assert len(session.websocket.sent) == before
        assert "completed document: make an Excel budget" in await voice_work_status_text(db_path)

    print("xai_realtime_work_supervisor_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
