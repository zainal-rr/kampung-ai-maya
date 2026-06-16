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

from assistant_commands import AssistantCommandRouter
from memory_service import MemoryService
from skill_registry import SkillRegistry
from storage import init_db
from voice_session_log import (
    finish_voice_session,
    record_voice_turn,
    start_voice_session,
)


async def main():
    with tempfile.TemporaryDirectory(prefix="maya-voice-log-smoke-") as tmp:
        os.environ["MAYA_WORKSPACE_ROOT"] = str(Path(tmp) / "Maya")
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        session_id = await start_voice_session(
            db_path,
            input_device="Zainal's Headphone",
            output_device="Zainal's Headphone",
            sample_rate=24000,
            model="grok-voice-latest",
            voice="ara",
        )
        await record_voice_turn(db_path, session_id, "user", "What time is it in Malaysia?")
        await record_voice_turn(db_path, session_id, "maya", "It is 2:30 PM in Malaysia.")
        await record_voice_turn(
            db_path,
            session_id,
            "system",
            "User speech started while Maya was responding; playback interrupted and response.cancel was sent.",
            interrupted=True,
        )
        await record_voice_turn(db_path, session_id, "user", "Count from four instead.")
        export_path = await finish_voice_session(
            db_path,
            session_id,
            close_reason="manual_stop",
            duration_seconds=12.4,
            input_device="Zainal's Headphone",
            output_device="Zainal's Headphone",
            audio_error_count=0,
            output_reset_count=0,
            transcript_count=2,
        )
        assert Path(export_path).exists()
        exported = Path(export_path).read_text(encoding="utf-8")
        assert "What time is it in Malaysia?" in exported
        assert "interrupted" in exported

        router = AssistantCommandRouter(db_path, MemoryService(db_path), SkillRegistry(db_path))
        last = await router.handle("show last voice session", "imac")
        assert last and "What time is it in Malaysia?" in last
        diagnostics = await router.handle("show voice session diagnostics", "imac")
        assert diagnostics and "close reason: manual_stop" in diagnostics
        today = await router.handle("show today voice sessions", "imac")
        assert today and "Session" in today
        search = await router.handle("search voice sessions for count", "imac")
        assert search and "Count from four" in search
        exported_reply = await router.handle("export last voice session", "imac")
        assert exported_reply and "voice_sessions" in exported_reply
    print("voice_session_log_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
