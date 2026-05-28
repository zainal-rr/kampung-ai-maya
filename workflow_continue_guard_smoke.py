from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from assistant import KampungAssistant
from context_layers import init_context_layers_db
from lesson_store import init_lesson_db
from route_tracker import last_route_text
from routine_store import init_routine_db
from session_memory_store import init_session_memory_db
from skill_store import init_skill_db
from storage import init_db


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-continue-guard-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)
        assistant = KampungAssistant(db_path)
        reply = await assistant.handle_text("continue", "telegram")
        _require(reply == "No active workflow right now.", "continue fell through without active workflow")
        route = await last_route_text(db_path)
        _require("LangGraph harness" in route and "Gemini" not in route, "continue reached model route")
        print("workflow_continue_guard_smoke: ok")


async def _init(db_path: str) -> None:
    for initializer in (
        init_db,
        init_lesson_db,
        init_skill_db,
        init_routine_db,
        init_session_memory_db,
        init_context_layers_db,
    ):
        await initializer(db_path)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
