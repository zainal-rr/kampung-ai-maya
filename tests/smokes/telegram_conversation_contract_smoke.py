from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import json
import logging
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiosqlite

from maya_core.assistant import KampungAssistant
from maya_core.assistant_routes import RouteResult
from maya_core.context_layers import init_context_layers_db
from harness_artifact_store import init_harness_artifact_db
from harness_store import init_harness_db
from lesson_store import init_lesson_db
from routine_store import init_routine_db
from session_memory_store import init_session_memory_db
from skill_store import init_skill_db
from storage import get_preference, init_db, save_history_message, upsert_preference


async def main() -> None:
    logging.disable(logging.CRITICAL)
    with tempfile.TemporaryDirectory(prefix="maya-telegram-contract-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)
        assistant = KampungAssistant(db_path)

        await _greeting_case(assistant, db_path)
        await _natural_memory_forget_case(assistant)
        await _short_followup_case(assistant, db_path)
        await _false_file_claim_case(assistant)
        await _false_memory_delete_claim_case(assistant)
        await _document_failure_no_fallback_case(assistant)
        await _stale_state_cleanup_case(assistant, db_path)
    print("telegram_conversation_contract_smoke: ok")


async def _greeting_case(assistant: KampungAssistant, db_path: str) -> None:
    await upsert_preference(
        db_path,
        "maya_pending_artifact_request:telegram",
        json.dumps({"topic": "Old Tokyo document", "created_at": (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()}),
        source="document",
    )
    reply = await assistant.handle_text("Hello maya", "telegram")
    _require("i’m here" in reply.lower() or "i'm here" in reply.lower(), f"weak greeting: {reply}")
    _require("send me something real" not in reply.lower(), f"old empty fallback leaked: {reply}")
    _require(await get_preference(db_path, "maya_pending_artifact_request:telegram") is None, "expired pending artifact was not cleared")


async def _natural_memory_forget_case(assistant: KampungAssistant) -> None:
    saved = await assistant.handle_text("Remember that my favorite airline is AirAsia", "telegram")
    _require("learned and saved" in saved.lower(), f"memory save failed: {saved}")
    recalled = await assistant.handle_text("What is my favorite airline?", "telegram")
    _require("AirAsia" in recalled, f"memory recall failed before forget: {recalled}")
    forgotten = await assistant.handle_text("Forget my favorite airline", "telegram")
    lowered = forgotten.lower()
    _require("forget result" in lowered and "canonical memory: 1" in lowered, f"natural forget did not use real memory path: {forgotten}")
    after = await assistant.handle_text("What is my favorite airline?", "telegram")
    _require(after == "I don't have that saved yet.", f"forgotten memory leaked after natural forget: {after}")


async def _short_followup_case(assistant: KampungAssistant, db_path: str) -> None:
    await save_history_message(db_path, 1, "assistant", "Hey, I’m here. What do you need?", "telegram")

    async def fake_route(**kwargs):
        context = kwargs.get("topic_context", "")
        _require("Immediate previous assistant reply" in context, f"missing immediate context: {context}")
        _require("documents you asked for" not in context.lower(), f"old artifact context leaked: {context}")
        return RouteResult("I meant I’m here and ready for your next request.", "Gemini Flash text", "normal Telegram text", True)

    assistant.router.route = fake_route
    reply = await assistant.handle_text("What do you meanv", "telegram")
    _require("documents" not in reply.lower(), f"follow-up hallucinated documents: {reply}")


async def _false_file_claim_case(assistant: KampungAssistant) -> None:
    async def fake_route(**_kwargs):
        return RouteResult(
            "I've drafted the documents you asked for: PowerPoint, Word, and Excel.",
            "Gemini Flash text",
            "normal Telegram text",
            True,
        )

    assistant.router.route = fake_route
    reply = await assistant.handle_text("What do you meanv", "telegram")
    lowered = reply.lower()
    _require("have not created or sent a file" in lowered, f"false file claim was not blocked: {reply}")
    _require("drafted the documents" not in lowered, f"false claim leaked: {reply}")


async def _false_memory_delete_claim_case(assistant: KampungAssistant) -> None:
    async def fake_route(**_kwargs):
        return RouteResult(
            "Done. I've cleared that airline preference from my memory.",
            "Gemini Flash text",
            "normal Telegram text",
            True,
        )

    assistant.router.route = fake_route
    reply = await assistant.handle_text("Can you clear that airline preference?", "telegram")
    lowered = reply.lower()
    _require("have not changed memory" in lowered, f"false memory delete claim was not blocked: {reply}")
    _require("cleared that airline preference" not in lowered, f"false memory delete claim leaked: {reply}")


async def _document_failure_no_fallback_case(assistant: KampungAssistant) -> None:
    async def broken_command_handle(_text: str, _channel: str):
        raise RuntimeError("simulated document router failure")

    async def fake_route(**_kwargs):
        return RouteResult("This is normal chat fallback.", "Gemini Flash text", "normal Telegram text", True)

    assistant.commands.handle = broken_command_handle
    assistant.router.route = fake_route
    reply = await assistant.handle_text("Make me a Tokyo itinerary Word document", "telegram")
    lowered = reply.lower()
    _require("document tool failed before delivery" in lowered, f"document failure was not explicit: {reply}")
    _require("normal chat fallback" not in lowered, f"document failure fell through to chat: {reply}")


async def _stale_state_cleanup_case(assistant: KampungAssistant, db_path: str) -> None:
    expired = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO artifact_sessions
                (channel, artifact_type, path, short_name, title, topic, state_json, revision, status, created_at, updated_at, expires_at)
            VALUES ('telegram', 'xlsx', '/tmp/old.xlsx', 'old', 'Old', 'Old budget', '{}', 0, 'active', ?, ?, ?)
            """,
            (expired, expired, expired),
        )
        await db.commit()

    await assistant.handle_text("Hi maya", "telegram")
    async with aiosqlite.connect(db_path) as db:
        row = await (await db.execute("SELECT status FROM artifact_sessions WHERE path = '/tmp/old.xlsx'")).fetchone()
    _require(row and row[0] == "inactive", f"expired artifact session was not inactivated: {row}")


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)
    await init_session_memory_db(db_path)
    await init_context_layers_db(db_path)
    await init_harness_db(db_path)
    await init_harness_artifact_db(db_path)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
