from __future__ import annotations

import os

from artisan_route_policy import should_use_artisan_path as artisan_route_should_use
from artisan_runner import create_artisan_implementation_request
from complex_agentic_bridge import should_route_complex_plan
from complex_lane import complex_plan_response as run_complex_plan_response
from cost_tracker import record_usage
from language_policy import language_instruction
from models import TheMind, TheNews, TheSenses, TheSteward
from orchestrator_prompts import MIND_ESCALATION_PROMPT
from provider_capabilities import CAPABILITIES, review_triggers
from source_aware_research import format_source_research, should_use_source_research, source_aware_research
from weather_lookup import current_weather_summary, is_weather_question


class ModelLanes:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path
        self.mind = TheMind(os.getenv("OPENAI_API_KEY", "dummy"))
        self.sight = TheSenses(os.getenv("GOOGLE_API_KEY", "dummy"))
        self.pulse = TheNews(os.getenv("XAI_API_KEY", "dummy"))
        self.premium_sight = TheSenses(
            os.getenv("GOOGLE_API_KEY", "dummy"),
            os.getenv("GEMINI_PREMIUM_MODEL", "gemini-3.5-flash"),
        )
        self.steward = TheSteward(
            os.getenv("ANTHROPIC_API_KEY", "dummy"),
            os.getenv("CLAUDE_STEWARD_MODEL", CAPABILITIES["steward"].default_model),
        )

    @staticmethod
    def build_imac_fast_responder():
        xai_api_key = os.getenv("XAI_API_KEY")
        if xai_api_key:
            return TheNews(xai_api_key)
        return TheSenses(os.getenv("GOOGLE_API_KEY", "dummy"))

    @staticmethod
    def should_use_artisan_path(text: str) -> bool:
        return artisan_route_should_use(text)

    @staticmethod
    def artisan_lane() -> str:
        return "Gemini build brief + Artisan Codex"

    @staticmethod
    def should_use_pulse_path(text: str) -> bool:
        lowered = text.lower()
        markers = (
            "latest news", "breaking news", "current events", "worldview",
            "weather", "stock", "market", "exchange rate", "currency",
            "myr", "usd", "x feed", "twitter",
        )
        return any(marker in lowered for marker in markers)

    @staticmethod
    def should_use_source_research_path(text: str) -> bool:
        return should_use_source_research(text)

    @staticmethod
    def should_use_complex_path(text: str) -> bool:
        lowered = text.lower()
        markers = (
            "this is complex", "this is a complex task", "this is a complex project",
            "complex task", "complex stuff", "complex question",
            "route to gpt", "route this to gpt", "use gpt", "gpt5.5", "gpt-5.5",
            "deep judgement", "important judgement",
        )
        return any(marker in lowered for marker in markers)

    @staticmethod
    def should_use_plan_path(text: str) -> bool:
        lowered = text.lower()
        return should_route_complex_plan(text) or lowered.startswith("plan ") or any(marker in lowered for marker in (" plan", "make a plan", "planning", "implementation plan"))

    @staticmethod
    def should_use_steward_path(text: str) -> bool:
        lowered = text.lower()
        return any(marker in lowered for marker in review_triggers())

    async def complex_response(self, text: str, memory_context: str, skill_context: str) -> str:
        if not os.getenv("OPENAI_API_KEY"):
            return "The complex lane is not available yet. Add the strategic API key first."
        prompt = self._prompt(MIND_ESCALATION_PROMPT, text, memory_context, skill_context)
        effort = os.getenv("OPENAI_COMPLEX_REASONING_EFFORT", "medium")
        reply = await self.mind.chat(prompt, reasoning_effort=effort)
        await record_usage(self.db_path, "gpt_complex_calls", 1, "telegram complex")
        return reply

    async def complex_plan_response(self, text: str, memory_context: str, skill_context: str, channel: str = "telegram") -> str:
        return await run_complex_plan_response(self, text, memory_context, skill_context, channel)

    async def artisan_response(self, text: str, memory_context: str, skill_context: str, channel: str = "telegram") -> str:
        if not os.getenv("GOOGLE_API_KEY"):
            return "Artisan needs Gemini to create the build brief first. Gemini is not available yet."
        brief = await self._artisan_build_brief(text, memory_context, skill_context)
        await record_usage(self.db_path, "gemini_flash_text_calls", 1, "artisan build brief")
        _, reply = await create_artisan_implementation_request(
            self.db_path,
            text,
            channel,
            gemini_build_brief=brief,
        )
        return reply

    async def _artisan_build_brief(self, text: str, memory_context: str, skill_context: str) -> str:
        prompt = self._prompt(
            (
                "You are Maya's Gemini build-brief creator. Create a compact implementation brief "
                "for The Artisan, who runs Codex locally. Do not write the implementation. "
                "Return plain text with: artifact intent, user goal, project scope, target folder, "
                "required files, constraints, acceptance criteria, safety boundaries, test plan, "
                "and assumptions. If this is app-building, require a real project folder. If this is "
                "Blender or 3D printing, require editable source files and stop before physical print."
            ),
            text,
            memory_context,
            skill_context,
        )
        brief = await self.sight.chat(prompt)
        if not brief.strip():
            raise RuntimeError("Gemini returned no Artisan build brief.")
        return brief

    async def steward_response(self, text: str, memory_context: str, skill_context: str) -> str:
        if not os.getenv("ANTHROPIC_API_KEY"):
            return "The review lane is not available yet. Add the Claude steward API key first."
        prompt = self._prompt(
            "You are Maya's Steward lane. Review carefully, find hidden risks, "
            "check clarity and safety, and recommend practical corrections. "
            "Do not take over execution.",
            text,
            memory_context,
            skill_context,
        )
        reply = await self.steward.chat(prompt)
        await record_usage(self.db_path, "claude_steward_calls", 1, "review")
        return reply

    async def post_implementation_review(
        self,
        request: str,
        approved_plan: str,
        implementation_summary: str,
        test_output: str,
    ) -> str:
        if not os.getenv("ANTHROPIC_API_KEY"):
            return "Post-implementation Steward review is unavailable until the Claude key is added."
        prompt = self._prompt(
            "Review the completed implementation against the approved plan and tests. "
            "Flag mismatches, missing verification, safety issues, and follow-up fixes. Do not implement.",
            (
                f"Request:\n{request}\n\nApproved plan:\n{approved_plan}\n\n"
                f"Implementation summary:\n{implementation_summary}\n\nTest output:\n{test_output}"
            ),
            "",
            "",
        )
        review = await self.steward.chat(prompt)
        await record_usage(self.db_path, "claude_steward_calls", 1, "post implementation review")
        return review

    async def pulse_response(self, text: str, memory_context: str, skill_context: str) -> str:
        if not os.getenv("XAI_API_KEY"):
            return "The live news lane is not available yet. Add the xAI key first."
        live_context = ""
        if is_weather_question(text):
            try:
                live_context = await current_weather_summary(text) or ""
            except Exception:
                live_context = ""
        system = "You are Maya's live pulse lane. Answer current questions briefly."
        context = "\n\n".join(block for block in (memory_context, skill_context, live_context) if block)
        prompt = self._prompt(system, text, context, "")
        reply = await self.pulse.chat(prompt)
        await record_usage(self.db_path, "grok_text_calls", 1, "current question")
        return reply

    async def source_research_response(
        self,
        text: str,
        memory_context: str,
        skill_context: str,
        channel: str = "telegram",
    ) -> str:
        result = await source_aware_research(
            self.db_path or "",
            text,
            memory_context=memory_context,
            skill_context=skill_context,
        )
        return format_source_research(result, channel=channel)

    @staticmethod
    def _prompt(system_prompt: str, text: str, memory_context: str, skill_context: str) -> list[dict[str, str]]:
        support_context = "\n\n".join(block for block in (memory_context, skill_context) if block)
        return [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": language_instruction(text)},
            {"role": "system", "content": support_context or "No extra support context."},
            {"role": "user", "content": text},
        ]
