from __future__ import annotations
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

from maya_core.assistant import KampungAssistant
from maya_core.cost_tracker import usage_summary_text
from maya_core.lesson_store import init_lesson_db
from maya_core.routine_store import init_routine_db
from maya_core.route_tracker import last_route_text
from session_search import search_sessions
from skill_store import init_skill_db
from storage import get_history, init_db, upsert_preference


class FakeResponder:
    def __init__(self, reply: str):
        self.reply = reply
        self.calls = 0
        self.messages = []

    async def chat(self, messages):
        self.calls += 1
        self.messages = messages
        return self.reply


class FakeModelLanes:
    def __init__(self):
        self.artisan_calls = 0
        self.complex_calls = 0
        self.pulse_calls = 0
        self.steward_calls = 0

    @staticmethod
    def should_use_artisan_path(text: str) -> bool:
        return "python" in text.lower() or "debug" in text.lower()

    @staticmethod
    def artisan_lane() -> str:
        return "Gemini build brief + Artisan Codex"

    @staticmethod
    def should_use_pulse_path(text: str) -> bool:
        return "latest news" in text.lower()

    @staticmethod
    def should_use_complex_path(text: str) -> bool:
        return "complex task" in text.lower()

    @staticmethod
    def should_use_plan_path(text: str) -> bool:
        return "plan" in text.lower()

    @staticmethod
    def should_use_steward_path(text: str) -> bool:
        return "check this plan carefully" in text.lower()

    @staticmethod
    def should_use_source_research_path(text: str) -> bool:
        return False

    async def artisan_response(self, text: str, memory_context: str, skill_context: str, channel: str = "telegram") -> str:
        self.artisan_calls += 1
        return "artisan lane"

    async def complex_response(self, text: str, memory_context: str, skill_context: str) -> str:
        self.complex_calls += 1
        return "complex lane"

    async def complex_plan_response(self, text: str, memory_context: str, skill_context: str, channel: str = "telegram") -> str:
        self.complex_calls += 1
        return "complex plan lane"

    async def pulse_response(self, text: str, memory_context: str, skill_context: str) -> str:
        self.pulse_calls += 1
        return "pulse lane"

    async def steward_response(self, text: str, memory_context: str, skill_context: str) -> str:
        self.steward_calls += 1
        return "steward lane"


async def main() -> None:
    os.environ["GOOGLE_API_KEY"] = "test-google-key"
    with tempfile.TemporaryDirectory(prefix="maya-routing-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)
        assistant = KampungAssistant(db_path)
        assistant.telegram_fast_responder = FakeResponder("fast telegram lane")
        assistant.model_lanes = FakeModelLanes()

        normal = await assistant.handle_text("think through architecture strategy", "telegram")
        _require("fast telegram lane" in normal, "normal Telegram should stay on Gemini fast lane")
        route = await last_route_text(db_path)
        _require("lane: Gemini Flash text" in route and "cost recorded: yes" in route, "Gemini Telegram route should record cost")
        usage = await usage_summary_text(db_path)
        _require("Gemini Flash text: 1 calls" in usage, "Gemini Telegram usage was not tracked")

        complex_answer = await assistant.handle_text("[complex]think through architecture strategy", "telegram")
        _require("complex lane" in complex_answer, "complex marker should use GPT lane")

        plan_answer = await assistant.handle_text("[complex]make a plan for architecture", "telegram")
        _require("complex plan lane" in plan_answer, "complex plan should use GPT plan lane")

        imac_complex = await assistant.handle_text("this is a complex task about architecture", "imac")
        _require("complex lane" in imac_complex, "iMac complex cue should use GPT lane")

        code = await assistant.handle_text("debug this python function", "telegram")
        _require("artisan lane" in code, "coding question should use Artisan lane")
        memory_recall = await assistant.handle_text("what is my Telegram test city?", "telegram")
        _require(memory_recall == "I don't have that saved yet.", "unknown direct memory recall should not guess")
        route = await last_route_text(db_path)
        _require("lane: command" in route and "reason: memory lookup" in route, "direct memory recall should use command lane")
        _require("coding" not in route.lower(), "memory recall with word test should not use coding lane")
        await upsert_preference(db_path, "lesson_global_my_test_city", "my Telegram test city is Kuala Lumpur", source="telegram")
        await upsert_preference(db_path, "lesson_global_my_test_drink", "my Telegram test drink is teh ais", source="telegram")
        known_memory = await assistant.handle_text("what is my Telegram test city?", "telegram")
        _require("Kuala Lumpur" in known_memory, "known direct memory recall should return saved value")
        _require("teh ais" not in known_memory, "known direct memory recall should not include nearby facts")
        known_drink = await assistant.handle_text("what is my Telegram test drink?", "telegram")
        _require(known_drink.count("teh ais") == 1, "known direct memory recall should deduplicate exact fact")
        _require("Kuala Lumpur" not in known_drink, "known direct memory recall should not include overlapping facts")

        news = await assistant.handle_text("latest news today", "telegram")
        _require("pulse lane" in news, "latest news should use Pulse lane")

        malay_news = await assistant.handle_text("berita latest hari ini macam mana", "telegram")
        _require("fast telegram lane" in malay_news, "Malay or Manglish Telegram should use Gemini instead of Grok")

        see = await assistant.handle_text("/see", "telegram")
        route = await last_route_text(db_path)
        _require("lane: command" in route and "reason: /see" in route, "/see should stay a direct command")

        unknown = await assistant.handle_text("/Desktop", "telegram")
        _require("not in the command list" in unknown, "unknown slash command should not become workflow")
        route = await last_route_text(db_path)
        _require("lane: command" in route and "reason: /desktop" in route, "unknown slash command should be direct")

        review = await assistant.handle_text("check this plan carefully before acting", "telegram")
        _require("steward lane" in review, "review question should use Steward lane")

        calls_before_presence = assistant.telegram_fast_responder.calls
        voice = await assistant.handle_text("are you there", "telegram", input_type="voice note")
        _require(voice == "I'm here.", "presence voice note should stay natural and direct")
        _require(
            assistant.telegram_fast_responder.calls == calls_before_presence,
            "presence voice note should not borrow model context",
        )
        voice_system = assistant.telegram_fast_responder.messages[0]["content"]
        history = await get_history(db_path, 1, limit=2)
        _require(history[-2]["content"] == "are you there", "voice transcript was not stored as user history")
        _require(history[-1]["content"] == "I'm here.", "voice answer was not stored as assistant history")
        session_rows = await search_sessions(db_path, "there", limit=3)
        _require(
            any(row["role"] == "user" and row["channel"] == "telegram" for row in session_rows),
            "voice transcript was not indexed with Telegram channel",
        )
        voice_route = await last_route_text(db_path)
        _require("lane: xAI STT + policy" in voice_route, "presence voice route should show STT plus policy lane")
        _require("model: grok-2-audio" in voice_route.lower(), "presence voice route should only claim STT")
        _require("reason: voice note transcribed, then curated system answer" in voice_route, "voice route reason should mention transcription")
        _require("cost recorded: yes" in voice_route, "voice route should record paid STT cost")

        misheard_presence = await assistant.handle_text("Are you dead?", "telegram", input_type="voice note")
        _require(misheard_presence == "I'm here.", "common STT presence mishear should stay policy-routed")
        misheard_route = await last_route_text(db_path)
        _require("lane: xAI STT + policy" in misheard_route, "misheard presence should show STT plus policy lane")

        voice_model = await assistant.handle_text("explain quantum spin simply", "telegram", input_type="voice note")
        _require("fast telegram lane" in voice_model, "non-presence voice note should answer through normal Telegram lane")
        voice_system = assistant.telegram_fast_responder.messages[0]["content"]
        _require("Telegram voice note" in voice_system, "voice notes should use the spoken Telegram prompt")
        _require("Do not use numbered lists" in voice_system, "voice prompt should block document-style outlines")

        sight = await assistant.handle_text("[sight]karang satu cerita pendek", "imac")
        _require("fast telegram lane" in sight, "explicit sight route should use Gemini fast lane")

        print("telegram_routing_smoke: ok")


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
