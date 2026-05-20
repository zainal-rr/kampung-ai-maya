from __future__ import annotations

import os

from cost_tracker import record_usage
from language_policy import language_instruction
from models import TheHands, TheMind, TheNews, TheSenses, TheSteward
from orchestrator_prompts import ARTISAN_SYSTEM_PROMPT, MIND_ESCALATION_PROMPT, TECHNICAL_KEYWORDS
from provider_capabilities import CAPABILITIES, review_triggers


class ModelLanes:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path
        self.mind = TheMind(os.getenv("OPENAI_API_KEY", "dummy"))
        self.artisan = TheHands(os.getenv("KIMI_API_KEY", "dummy"))
        self.pulse = TheNews(os.getenv("XAI_API_KEY", "dummy"))
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
        upper = text.upper()
        return any(keyword in upper for keyword in TECHNICAL_KEYWORDS)

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
        return lowered.startswith("plan ") or any(marker in lowered for marker in (" plan", "make a plan", "planning", "implementation plan"))

    @staticmethod
    def should_use_steward_path(text: str) -> bool:
        lowered = text.lower()
        return any(marker in lowered for marker in review_triggers())

    async def complex_response(self, text: str, memory_context: str, skill_context: str) -> str:
        if not os.getenv("OPENAI_API_KEY"):
            return "The complex lane is not available yet. Add the strategic API key first."
        prompt = self._prompt(MIND_ESCALATION_PROMPT, text, memory_context, skill_context)
        effort = os.getenv("OPENAI_COMPLEX_REASONING_EFFORT", "xhigh")
        reply = await self.mind.chat(prompt, reasoning_effort=effort)
        await record_usage(self.db_path, "gpt_complex_calls", 1, "telegram complex")
        return reply

    async def complex_plan_response(self, text: str, memory_context: str, skill_context: str) -> str:
        if not os.getenv("OPENAI_API_KEY"):
            return "The complex planning lane is not available yet. Add the strategic API key first."
        plan_prompt = self._prompt(
            MIND_ESCALATION_PROMPT + "\nProduce a Codex-style plan only. Do not execute. Include Summary, Key Changes, Test Plan, Assumptions, and Approval Needed.",
            text,
            memory_context,
            skill_context,
        )
        effort = os.getenv("OPENAI_COMPLEX_REASONING_EFFORT", "xhigh")
        plan = await self.mind.chat(plan_prompt, reasoning_effort=effort)
        review = await self._review_plan(text, plan, memory_context, skill_context)
        await record_usage(self.db_path, "gpt_complex_calls", 1, "complex plan")
        return _merge_plan_review(plan, review)

    async def artisan_response(self, text: str, memory_context: str, skill_context: str) -> str:
        if not os.getenv("KIMI_API_KEY"):
            return "The coding lane is not available yet. Add the builder API key first."
        prompt = self._prompt(ARTISAN_SYSTEM_PROMPT, text, memory_context, skill_context)
        reply = await self.artisan.chat(prompt)
        await record_usage(self.db_path, "kimi_coding_calls", 1, "coding question")
        return reply

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

    async def _review_plan(self, text: str, plan: str, memory_context: str, skill_context: str) -> str:
        if not os.getenv("ANTHROPIC_API_KEY"):
            return "Steward review unavailable until the Claude key is added."
        prompt = self._prompt(
            "Review this GPT plan before implementation. Check hidden risks, missing assumptions, "
            "safety issues, overengineering, unclear tests, and practical gaps. Do not implement.",
            f"Original request:\n{text}\n\nPlan to review:\n{plan}",
            memory_context,
            skill_context,
        )
        review = await self.steward.chat(prompt)
        await record_usage(self.db_path, "claude_steward_calls", 1, "complex plan review")
        return review

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
        prompt = self._prompt("You are Maya's live pulse lane. Answer current questions briefly.", text, memory_context, skill_context)
        reply = await self.pulse.chat(prompt)
        await record_usage(self.db_path, "grok_text_calls", 1, "current question")
        return reply

    @staticmethod
    def _prompt(system_prompt: str, text: str, memory_context: str, skill_context: str) -> list[dict[str, str]]:
        support_context = "\n\n".join(block for block in (memory_context, skill_context) if block)
        return [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": language_instruction(text)},
            {"role": "system", "content": support_context or "No extra support context."},
            {"role": "user", "content": text},
        ]


def _merge_plan_review(plan: str, review: str) -> str:
    return f"{plan.strip()}\n\nSteward review:\n{review.strip()}"
