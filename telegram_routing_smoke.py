from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from assistant import KampungAssistant
from lesson_store import init_lesson_db
from routine_store import init_routine_db
from skill_store import init_skill_db
from storage import init_db


class FakeResponder:
    def __init__(self, reply: str):
        self.reply = reply
        self.calls = 0

    async def chat(self, messages):
        self.calls += 1
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

    async def artisan_response(self, text: str, memory_context: str, skill_context: str) -> str:
        self.artisan_calls += 1
        return "artisan lane"

    async def complex_response(self, text: str, memory_context: str, skill_context: str) -> str:
        self.complex_calls += 1
        return "complex lane"

    async def complex_plan_response(self, text: str, memory_context: str, skill_context: str) -> str:
        self.complex_calls += 1
        return "complex plan lane"

    async def pulse_response(self, text: str, memory_context: str, skill_context: str) -> str:
        self.pulse_calls += 1
        return "pulse lane"

    async def steward_response(self, text: str, memory_context: str, skill_context: str) -> str:
        self.steward_calls += 1
        return "steward lane"


class ForbiddenOrchestrator:
    async def run(self, user_input: str, history=None):
        raise AssertionError("Telegram should not auto-route through orchestrator")


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-routing-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)
        assistant = KampungAssistant(db_path)
        assistant.orchestrator = ForbiddenOrchestrator()
        assistant.telegram_fast_responder = FakeResponder("fast telegram lane")
        assistant.model_lanes = FakeModelLanes()

        normal = await assistant.handle_text("think through architecture strategy", "telegram")
        _require("fast telegram lane" in normal, "normal Telegram should stay on Gemini fast lane")

        complex_answer = await assistant.handle_text("[complex]think through architecture strategy", "telegram")
        _require("complex lane" in complex_answer, "complex marker should use GPT lane")

        plan_answer = await assistant.handle_text("[complex]make a plan for architecture", "telegram")
        _require("complex plan lane" in plan_answer, "complex plan should use GPT plan lane")

        imac_complex = await assistant.handle_text("this is a complex task about architecture", "imac")
        _require("complex lane" in imac_complex, "iMac complex cue should use GPT lane")

        code = await assistant.handle_text("debug this python function", "telegram")
        _require("artisan lane" in code, "coding question should use Artisan lane")

        news = await assistant.handle_text("latest news today", "telegram")
        _require("pulse lane" in news, "latest news should use Pulse lane")

        review = await assistant.handle_text("check this plan carefully before acting", "telegram")
        _require("steward lane" in review, "review question should use Steward lane")

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
