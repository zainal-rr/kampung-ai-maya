import asyncio
import json
import tempfile
import time
from pathlib import Path

import xai_realtime_events
from storage import init_db
from xai_realtime_events import XaiRealtimeEventMixin, _supervised_browser_request
from xai_realtime_models import PlaybackCommand


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
    assert _supervised_browser_request("Can you Google search Kazakhstan for me?")
    assert _supervised_browser_request("google images Pokemon")
    assert _supervised_browser_request("find flight to Penang on June 7")
    assert not _supervised_browser_request("what are you doing?")
    assert not _supervised_browser_request("how will you search at the back end?")

    original = xai_realtime_events.execute_voice_tool

    async def slow_browser_tool(*args, **kwargs):
        await asyncio.sleep(0.1)
        return "Request: Google search Kazakhstan\nStatus: completed\nResult:\nGoogle Search opened Kazakhstan."

    try:
        xai_realtime_events.execute_voice_tool = slow_browser_tool
        with tempfile.TemporaryDirectory(prefix="maya-browser-supervisor-") as tmp:
            db_path = str(Path(tmp) / "smoke.db")
            await init_db(db_path)
            session = FakeRealtimeSession(db_path)
            await session.playback_queue.put(PlaybackCommand("audio", b"old audio"))

            await session._maybe_start_supervised_browser_work("Can you Google search Kazakhstan for me?")
            assert session.drop_audio_until_next_response is False
            assert session.response_active is False
            assert session.playback_queue.empty()
            assert session.websocket.sent[0] == {"type": "response.cancel"}
            assert session.websocket.sent[1]["type"] == "conversation.item.create"
            assert "Say exactly this short acknowledgement" in session.websocket.sent[1]["item"]["content"][0]["text"]
            assert session.websocket.sent[2] == {"type": "response.create"}
            assert len(session.function_call_tasks) == 1

            started = time.monotonic()
            cancelled = await session._cancel_auto_response_for_supervised_browser()
            assert cancelled is False
            assert time.monotonic() - started < 0.05

            await asyncio.gather(*session.function_call_tasks)
            assert session.websocket.sent[-2]["type"] == "conversation.item.create"
            assert session.websocket.sent[-2]["item"]["role"] == "user"
            assert "Do not call another tool" in session.websocket.sent[-2]["item"]["content"][0]["text"]
            assert session.websocket.sent[-1] == {"type": "response.create"}
    finally:
        xai_realtime_events.execute_voice_tool = original
    print("xai_realtime_browser_supervisor_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
