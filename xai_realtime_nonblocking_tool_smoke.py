import asyncio
import json
import tempfile
import time
from pathlib import Path

import xai_realtime_events
from storage import init_db
from xai_realtime_events import XaiRealtimeEventMixin


class FakeWebSocket:
    def __init__(self):
        self.sent = []

    async def send(self, payload):
        self.sent.append(json.loads(payload))


class FakeRealtimeSession(XaiRealtimeEventMixin):
    def __init__(self, db_path):
        self.db_path = db_path
        self.voice_log_session_id = None
        self.current_response_id = "resp_smoke"
        self.function_call_tasks = set()
        self.stop_event = asyncio.Event()
        self.websocket = FakeWebSocket()
        self.assistant = None


async def main():
    original = xai_realtime_events.execute_voice_tool

    async def slow_tool(*args, **kwargs):
        await asyncio.sleep(0.15)
        return "slow result"

    try:
        xai_realtime_events.execute_voice_tool = slow_tool
        with tempfile.TemporaryDirectory(prefix="maya-realtime-nonblocking-") as tmp:
            db_path = str(Path(tmp) / "smoke.db")
            await init_db(db_path)
            session = FakeRealtimeSession(db_path)
            event = {
                "name": "run_browser_skill",
                "call_id": "call_smoke",
                "arguments": json.dumps({"request": "search modern kampung house"}),
            }
            started = time.monotonic()
            await session._handle_function_call(event)
            elapsed = time.monotonic() - started
            assert elapsed < 0.05, f"function call handler blocked for {elapsed:.3f}s"
            assert len(session.function_call_tasks) == 1
            await asyncio.gather(*session.function_call_tasks)
            assert session.websocket.sent[0]["type"] == "conversation.item.create"
            assert session.websocket.sent[0]["item"]["type"] == "function_call_output"
            assert session.websocket.sent[0]["item"]["output"] == "slow result"
            assert session.websocket.sent[1] == {"type": "response.create"}
    finally:
        xai_realtime_events.execute_voice_tool = original
    print("xai_realtime_nonblocking_tool_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
