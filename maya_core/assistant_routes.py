from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from assistant_reply_paths import fast_imac_response, fast_telegram_response
from assistant_text import clean_model_text, strip_wake_prefix
from language_policy import uses_malay_or_manglish, wants_malay_or_manglish
from response_style import format_grouped_answers, split_telegram_segments


@dataclass(frozen=True)
class RouteResult:
    response: str
    lane: str
    reason: str
    cost_recorded: bool = False


class AssistantRouter:
    def __init__(
        self,
        *,
        commands: Any,
        learning: Any,
        policy: Any,
        model_lanes: Any,
        telegram_fast_responder: Any,
        imac_fast_responder: Any,
    ):
        self.commands = commands
        self.learning = learning
        self.policy = policy
        self.model_lanes = model_lanes
        self.telegram_fast_responder = telegram_fast_responder
        self.imac_fast_responder = imac_fast_responder

    async def route(
        self,
        *,
        text: str,
        channel: str,
        complex_route: bool,
        sight_route: bool,
        history: list[dict[str, str]],
        request_text: str,
        memory_context: str,
        skill_context: str,
        topic_context: str,
        input_type: str = "text",
    ) -> RouteResult:
        try:
            return await self._route_inner(
                text=text,
                channel=channel,
                complex_route=complex_route,
                sight_route=sight_route,
                history=history,
                request_text=request_text,
                memory_context=memory_context,
                skill_context=skill_context,
                topic_context=topic_context,
                input_type=input_type,
            )
        except Exception:
            logging.exception("Assistant request failed on channel %s", channel)
            return RouteResult("Something went wrong on my side. Try again in a bit.", "error", "request failed")

    async def _route_inner(
        self,
        *,
        text: str,
        channel: str,
        complex_route: bool,
        sight_route: bool,
        history: list[dict[str, str]],
        request_text: str,
        memory_context: str,
        skill_context: str,
        topic_context: str,
        input_type: str,
    ) -> RouteResult:
        voice_note = input_type == "voice note"
        if complex_route:
            if self.model_lanes.should_use_plan_path(text):
                response = await self.model_lanes.complex_plan_response(text, memory_context, skill_context, channel)
                return RouteResult(response, "GPT 5.5 medium + Claude review", "explicit complex plan", bool(os.getenv("OPENAI_API_KEY")))
            response = await self.model_lanes.complex_response(text, memory_context, skill_context)
            return RouteResult(response, "GPT 5.5 medium", "explicit /complex", bool(os.getenv("OPENAI_API_KEY")))
        command_response = await self.commands.handle(text, channel)
        if command_response is not None:
            return RouteResult(command_response, "command", "app state or command")
        if sight_route:
            response = await fast_telegram_response(
                self.telegram_fast_responder,
                text,
                memory_context,
                skill_context,
                topic_context,
                voice_note=voice_note,
            )
            return RouteResult(response, "Gemini Flash text", "explicit sight quality route", bool(os.getenv("GOOGLE_API_KEY")))
        if channel == "imac" and self.model_lanes.should_use_complex_path(text):
            if self.model_lanes.should_use_plan_path(text):
                response = await self.model_lanes.complex_plan_response(text, memory_context, skill_context, channel)
                return RouteResult(response, "GPT 5.5 medium + Claude review", "explicit iMac complex plan", bool(os.getenv("OPENAI_API_KEY")))
            response = await self.model_lanes.complex_response(text, memory_context, skill_context)
            return RouteResult(response, "GPT 5.5 medium", "explicit iMac complex cue", bool(os.getenv("OPENAI_API_KEY")))
        if channel in {"telegram", "imac"} and self.model_lanes.should_use_artisan_path(text):
            response = await self.model_lanes.artisan_response(text, memory_context, skill_context, channel)
            return RouteResult(response, self.model_lanes.artisan_lane(), "coding implementation handoff", True)
        policy_response = self.policy.reply(text, channel)
        if policy_response is not None:
            return RouteResult(policy_response, "policy", "curated system answer")
        if self.model_lanes.should_use_steward_path(text):
            response = await self.model_lanes.steward_response(text, memory_context, skill_context)
            return RouteResult(response, "Claude Steward", "careful review request", bool(os.getenv("ANTHROPIC_API_KEY")))
        if channel == "imac" and self.model_lanes.should_use_source_research_path(text):
            response = await self.model_lanes.source_research_response(text, memory_context, skill_context, channel)
            return RouteResult(response, "Gemini source-aware research", "source-aware research", bool(os.getenv("GOOGLE_API_KEY")))
        if channel == "telegram":
            return await self._route_telegram(text, memory_context, skill_context, topic_context, voice_note)
        if channel == "imac":
            response = await fast_imac_response(self.imac_fast_responder, text, memory_context, skill_context)
            return RouteResult(response, "Grok voice/text", "normal iMac voice", bool(os.getenv("XAI_API_KEY")))
        response = await fast_telegram_response(
            self.telegram_fast_responder,
            text,
            memory_context,
            skill_context,
            topic_context,
            voice_note=voice_note,
        )
        return RouteResult(response, "Gemini Flash text", "default assistant text", bool(os.getenv("GOOGLE_API_KEY")))

    async def _route_telegram(
        self,
        text: str,
        memory_context: str,
        skill_context: str,
        topic_context: str,
        voice_note: bool = False,
    ) -> RouteResult:
        bundled_response = await self._handle_telegram_bundle(text, memory_context, skill_context, topic_context, voice_note)
        if bundled_response is not None:
            return RouteResult(bundled_response, "Gemini Flash text", "bundled Telegram text", bool(os.getenv("GOOGLE_API_KEY")))
        malay_or_manglish = uses_malay_or_manglish(text) or wants_malay_or_manglish(text)
        if self.model_lanes.should_use_pulse_path(text) and not malay_or_manglish:
            response = await self.model_lanes.pulse_response(text, memory_context, skill_context)
            return RouteResult(response, "Grok text/news", "current or news question", bool(os.getenv("XAI_API_KEY")))
        if self.model_lanes.should_use_source_research_path(text):
            response = await self.model_lanes.source_research_response(text, memory_context, skill_context, "telegram")
            return RouteResult(response, "Gemini source-aware research", "source-aware research", bool(os.getenv("GOOGLE_API_KEY")))
        response = await fast_telegram_response(
            self.telegram_fast_responder,
            text,
            memory_context,
            skill_context,
            topic_context,
            voice_note=voice_note,
        )
        return RouteResult(response, "Gemini Flash text", "normal Telegram text", bool(os.getenv("GOOGLE_API_KEY")))

    async def _answer_telegram_segment(
        self,
        segment: str,
        memory_context: str,
        skill_context: str,
        topic_context: str,
        voice_note: bool = False,
    ) -> str | None:
        normalized = " ".join(strip_wake_prefix(segment).split()).rstrip("?.! ")
        if not normalized:
            return None
        learning_response = await self.learning.handle(normalized, "telegram")
        if learning_response is not None:
            return clean_model_text(learning_response)
        command_response = await self.commands.handle(normalized, "telegram")
        if command_response is not None:
            return clean_model_text(command_response)
        policy_response = self.policy.reply(normalized, "telegram")
        if policy_response is not None:
            return policy_response
        return clean_model_text(
            await fast_telegram_response(
                self.telegram_fast_responder,
                normalized,
                memory_context,
                skill_context,
                topic_context,
                voice_note=voice_note,
            )
        )

    async def _handle_telegram_bundle(
        self,
        text: str,
        memory_context: str,
        skill_context: str,
        topic_context: str,
        voice_note: bool = False,
    ) -> str | None:
        segments = split_telegram_segments(text)
        if len(segments) < 2:
            return None
        answers = []
        for segment in segments:
            answer = await self._answer_telegram_segment(segment, memory_context, skill_context, topic_context, voice_note)
            if answer:
                answers.append(answer)
        if not answers:
            return None
        return answers[0] if len(answers) == 1 else format_grouped_answers(answers)
