# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys

import asyncio
import os
import tempfile
from pathlib import Path

from maya_voice.xai_realtime_stream import XaiRealtimeStreamingSession
from maya_voice.xai_realtime_stream_helpers import append_audio_message
from maya_voice.xai_realtime_tools import BROWSER_TOOL_NAME, HANDOFF_TOOL_NAME, MAYA_WORK_TOOL_NAME, execute_voice_tool
from maya_voice.tool_specs import FORGET_MEMORY_TOOL_NAME, RECALL_MEMORY_TOOL_NAME, SAVE_MEMORY_TOOL_NAME
from maya_voice.xai_voice_state_tools import read_maya_state
from maya_voice.xai_voice_work import voice_work_status_text
from maya_core.storage import init_db


class FakeAssistant:
    def __init__(self):
        self.handled = []

    async def handle_text(self, text, channel, speak_reply=False):
        self.handled.append((text, channel, speak_reply))
        return "Created the document at /Users/zainalabidinjamal/Desktop/Maya/documents/router-document-v1.docx and opened it."


async def main():
    os.environ["XAI_VOICE_AGENT_IDLE_SECONDS"] = "5"
    os.environ["XAI_VOICE_TURN_SILENCE_MS"] = "700"
    session = XaiRealtimeStreamingSession(":memory:", "test instructions")
    assert hasattr(session, "output_device_name")
    assert not hasattr(session, "call_output_device")
    assert not hasattr(session, "call_output_active")
    payload = session._session_update()
    assert payload["type"] == "session.update"
    assert payload["session"]["turn_detection"]["type"] == "server_vad"
    assert payload["session"]["turn_detection"]["silence_duration_ms"] == 700
    assert payload["session"]["voice"] == "ara"
    assert payload["session"]["input_audio_transcription"]["model"] == "grok-2-audio"
    tool_names = [tool["name"] for tool in payload["session"]["tools"] if tool.get("type") == "function"]
    assert SAVE_MEMORY_TOOL_NAME in tool_names
    assert RECALL_MEMORY_TOOL_NAME in tool_names
    assert FORGET_MEMORY_TOOL_NAME in tool_names
    assert tool_names.index(SAVE_MEMORY_TOOL_NAME) < tool_names.index("answer_with_gemini")
    assert tool_names.index(RECALL_MEMORY_TOOL_NAME) < tool_names.index("answer_with_gemini")
    assert tool_names.index(FORGET_MEMORY_TOOL_NAME) < tool_names.index("answer_with_gemini")
    assert "answer_with_gemini" in tool_names
    assert "read_maya_state" in tool_names
    assert "inspect_active_context" in tool_names
    assert BROWSER_TOOL_NAME in tool_names
    assert MAYA_WORK_TOOL_NAME in tool_names
    assert HANDOFF_TOOL_NAME not in tool_names
    assert "browser_task_step" not in tool_names
    assert "create_desktop_maya_file" not in tool_names
    assert "read_kampung_ai_context" not in tool_names
    assert "read_desktop_maya_workspace" not in tool_names
    assert "inspect_imac_screen" not in tool_names
    assert "inspect_maya_camera" not in tool_names
    assert "create_visual_workflow" not in tool_names
    assert "open_browser_for_task" not in tool_names
    assert "update_travel_plan" not in tool_names
    assert "read_call_context" not in tool_names
    assert "control_call_mode" not in tool_names
    assert "record_call_snippet" not in tool_names
    assert "save_call_summary" not in tool_names
    assert "check_call_audio_routes" not in tool_names
    assert "introduce_maya_to_call" not in tool_names
    assert "speak_to_call" not in tool_names
    assert payload["session"]["audio"]["input"]["format"]["type"] == "audio/pcm"
    assert payload["session"]["audio"]["output"]["format"]["rate"] == session.sample_rate
    assert append_audio_message(b"abc")["type"] == "input_audio_buffer.append"
    with tempfile.TemporaryDirectory(prefix="maya-voice-work-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        assistant = FakeAssistant()
        output = await execute_voice_tool(
            db_path,
            MAYA_WORK_TOOL_NAME,
            {"request": "make a Word document about routers"},
            assistant=assistant,
            voice_session_id="smoke",
        )
        assert "Status: completed" in output
        assert "/Users/zainalabidinjamal" not in output
        assert "the Maya documents folder (router-document-v1)" in output
        assert "handoff" not in output.lower()
        assert "paid voice" not in output.lower()
        assert assistant.handled == [("make a Word document about routers", "imac", False)]
        status = await voice_work_status_text(db_path)
        assert "done work: make a Word document about routers" in status
        assert "done work: make a Word document about routers" in await read_maya_state(db_path, "what are you doing")
        assert "Maya voice work:" in await read_maya_state(db_path, "status")
    os.environ["XAI_VOICE_ENABLE_SEARCH_TOOLS"] = "1"
    enabled_tools = session._session_update()["session"]["tools"]
    assert {"web_search", "x_search"}.isdisjoint({tool.get("type") for tool in enabled_tools})
    session.response_active = True
    await session._interrupt_playback()
    assert session.drop_audio_until_next_response is True
    assert session.response_active is False
    assert not hasattr(session, "_activate_call_output_for_response")
    print("xai_realtime_stream_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
