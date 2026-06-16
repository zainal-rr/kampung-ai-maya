from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path

from assistant import KampungAssistant
from briefing_service import BriefingBuilder
from health_monitor import HealthReporter
from routine_store import claim_due_routines, init_routine_db
from skill_store import init_skill_db
from storage import create_task, init_db
from time_parser import local_now


async def main() -> None:
    db_path = _temp_db()
    try:
        await init_db(db_path)
        await init_skill_db(db_path)
        await init_routine_db(db_path)
        assistant = KampungAssistant(db_path=db_path)

        results = {
            "routine_create": await assistant.handle_text(
                f"set up a morning briefing at {local_now().strftime('%I:%M %p')}",
                channel="imac",
                speak_reply=False,
            ),
            "routine_list": await assistant.handle_text("show my routines", channel="imac", speak_reply=False),
            "task_create": await assistant.handle_text(
                "remind me to review hosting renewal in 10 minutes",
                channel="telegram",
                speak_reply=False,
            ),
            "approval_prompt": await assistant.handle_text(
                "send my tasks to telegram",
                channel="telegram",
                speak_reply=False,
            ),
            "approval_decline": await assistant.handle_text("no", channel="telegram", speak_reply=False),
            "local_action": await assistant.handle_text("what app is open", channel="imac", speak_reply=False),
        }

        await create_task(
            db_path,
            title="Review hosting renewal",
            details="Check renewal status and next action",
            channel="imac",
            action_type="follow_up",
            autonomy_mode="auto_safe",
            due_at=local_now().isoformat(),
        )
        due = await claim_due_routines(db_path, local_now())
        briefing = await BriefingBuilder(db_path).build("morning_briefing", "imac")

        reporter = HealthReporter(db_path, log_dir="logs")
        await reporter.write_snapshot()
        health = json.loads((Path("logs") / "health.json").read_text(encoding="utf-8"))

        print(
            json.dumps(
                {
                    "results": results,
                    "due_routines": len(due),
                    "briefing_preview": briefing[:160],
                    "health_keys": sorted(health.keys()),
                },
                indent=2,
            )
        )
    finally:
        Path(db_path).unlink(missing_ok=True)


def _temp_db() -> str:
    fd, path = tempfile.mkstemp(prefix="kampung-rehearsal-", suffix=".db")
    os.close(fd)
    return path


if __name__ == "__main__":
    asyncio.run(main())
