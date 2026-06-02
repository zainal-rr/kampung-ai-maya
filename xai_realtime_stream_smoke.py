import asyncio
import os
import tempfile
from pathlib import Path

from xai_realtime_stream import XaiRealtimeStreamingSession
from xai_realtime_stream_helpers import append_audio_message
from xai_realtime_tools import HANDOFF_TOOL_NAME, execute_voice_tool
from xai_voice_handoff import pop_voice_handoff_request
from storage import init_db


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
    assert "answer_with_gemini" in tool_names
    assert "read_maya_state" in tool_names
    assert "inspect_active_context" in tool_names
    assert HANDOFF_TOOL_NAME in tool_names
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
    with tempfile.TemporaryDirectory(prefix="maya-voice-handoff-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        output = await execute_voice_tool(db_path, HANDOFF_TOOL_NAME, {"request": "make a Word document about routers"})
        assert "Handoff saved" in output
        assert await pop_voice_handoff_request(db_path) == "make a Word document about routers"
        assert await pop_voice_handoff_request(db_path) is None
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
