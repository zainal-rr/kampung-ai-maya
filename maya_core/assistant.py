import logging, os

from maya_documents.artifact_clarification_state import cleanup_expired_pending_artifact_request
from maya_documents.artifact_sessions import cleanup_expired_artifact_sessions
from maya_core.assistant_context_helpers import handle_context_command
from maya_core.assistant_text import clean_model_text, normalize_history, strip_wake_prefix
from maya_core.assistant_commands import AssistantCommandRouter
from maya_core.learning_pipeline import LearningPipeline
from maya_core.assistant_memory_context import build_assistant_memory_context
from maya_core.assistant_model_lanes import ModelLanes
from maya_core.assistant_post_route import maybe_curate_memory, route_metadata
from maya_core.assistant_reply_paths import prepare_input
from maya_core.assistant_route_prefixes import (
    COMPLEX_ROUTE_PREFIX,
    SIGHT_ROUTE_PREFIX,
    complex_payload,
    is_complex_route,
    is_sight_route,
    sight_payload,
)
from maya_core.assistant_routes import AssistantRouter, RouteResult
from maya_core.channel_gateway import remember_channel_identity
from maya_core.cost_tracker import record_usage
from maya_harness.harness_router import HarnessRouter
from maya_memory.memory_service import MemoryService
from maya_core.models import TheSenses
from response_policy import ResponsePolicy
from response_style import apply_reply_preferences
from route_tracker import record_route
from safety_action_commands import safety_action_reply
from screen_responder import ScreenResponder
from session_compactor import compact_if_needed
from skill_registry import SkillRegistry
from self_improvement_policy import enforce_honest_claims
from storage import get_history, save_history_message
from telegram_commands import PASSTHROUGH_COMMANDS, command_to_text, parse_command
from telegram_conversation_contract import enforce_telegram_truth_contract, strong_artifact_request, telegram_document_failure_reply, telegram_greeting_reply, telegram_short_followup_context
from telegram_rewrite_context import is_rewrite_followup, latest_rewrite_candidate, remember_rewrite_candidate, rewrite_context_prompt
from topic_context import format_topic_context, recent_topic_history
from voice import VoiceNode, spoken_preview
from voice_command_aliases import spoken_command_alias
from voice_transcript_policy import clean_voice_transcript_for_intent
from vision_responder import VisionResponder

PRIMARY_USER_ID = 1
class KampungAssistant:
    def __init__(self, db_path: str = "session_history.db"):
        self.db_path = db_path
        self.memory = MemoryService(db_path)
        self.skills = SkillRegistry(db_path)
        self.commands = AssistantCommandRouter(db_path, self.memory, self.skills)
        self.policy = ResponsePolicy()
        self.learning = LearningPipeline(db_path)
        self.vision_responder = VisionResponder(db_path)
        self.screen_responder = ScreenResponder(db_path)
        self.model_lanes = ModelLanes(db_path)
        self.harness = HarnessRouter(db_path, planner_llm=self.model_lanes.build_harness_planner())
        self.imac_fast_responder = self.model_lanes.build_imac_fast_responder()
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            logging.warning(
                "GOOGLE_API_KEY is not set; Telegram fast lane will fail on live calls. "
                "main.py enforces this at service startup via require_env."
            )
        self.telegram_fast_responder = TheSenses(google_api_key or "missing-google-api-key")
        self.router = AssistantRouter(
            commands=self.commands,
            learning=self.learning,
            policy=self.policy,
            model_lanes=self.model_lanes,
            telegram_fast_responder=self.telegram_fast_responder,
            imac_fast_responder=self.imac_fast_responder,
        )
        self.voice = VoiceNode(db_path)

    def _sync_router(self) -> None:
        self.router.commands = self.commands
        self.router.learning = self.learning
        self.router.policy = self.policy
        self.router.model_lanes = self.model_lanes
        self.router.telegram_fast_responder = self.telegram_fast_responder
        self.router.imac_fast_responder = self.imac_fast_responder
        self.harness.runner.tools.documents = self.commands.documents
        self.harness.runner.tools.drawing = self.commands.drawing
        self.harness.runner.tools.files = self.commands.files
        self.harness.runner.tools.workspace = self.commands.workspace
        self.harness.runner.tools.projects = self.commands.projects
        self.harness.runner.tools.imac = self.commands.workflows
        self.harness.runner.tools.browser = self.commands.workflows.human_browser
        self.harness.runner.tools.local = self.commands.actions

    async def handle_text(
        self,
        text: str,
        channel: str,
        speak_reply: bool = False,
        user_id: int = PRIMARY_USER_ID,
        input_type: str = "text",
        channel_external_id: str = "",
    ) -> str:
        original_text = text
        clean_text = strip_wake_prefix(text)
        if "voice" in input_type.lower():
            clean_text = clean_voice_transcript_for_intent(clean_text)
        if channel == "telegram":
            await cleanup_expired_pending_artifact_request(self.db_path, channel)
            await cleanup_expired_artifact_sessions(self.db_path, channel)
        if not clean_text:
            greeting = telegram_greeting_reply(original_text, clean_text) if channel == "telegram" else None
            if greeting:
                return greeting
            return "Send me something real and I'll take it from there."
        if channel_external_id:
            await remember_channel_identity(self.db_path, channel, channel_external_id)
        alias = spoken_command_alias(clean_text, channel=channel, input_type=input_type)
        if alias:
            clean_text = alias
        direct_command = parse_command(clean_text)
        if direct_command is not None:
            try:
                reply = await command_to_text(self.db_path, direct_command)
                if direct_command.name in PASSTHROUGH_COMMANDS or reply.startswith((COMPLEX_ROUTE_PREFIX, SIGHT_ROUTE_PREFIX)):
                    clean_text = reply
                else:
                    if direct_command.name != "route":
                        await record_route(self.db_path, "command", "command", f"/{direct_command.name}", False)
                    await save_history_message(self.db_path, user_id, "user", clean_text, channel)
                    await save_history_message(self.db_path, user_id, "assistant", reply, channel)
                    return reply
            except Exception:
                logging.exception("Direct slash command failed on channel %s", channel)

        complex_route = is_complex_route(clean_text)
        sight_route = is_sight_route(clean_text)
        if complex_route:
            clean_text = complex_payload(clean_text)
            if not clean_text:
                return "Use /complex followed by the question or decision you want me to think through."
        if sight_route:
            clean_text = sight_payload(clean_text)
            if not clean_text:
                return "Tell me what you want me to think through."

        history = normalize_history(await get_history(self.db_path, user_id))
        short_followup_context = telegram_short_followup_context(clean_text, history) if channel == "telegram" else ""
        topic_context = short_followup_context or format_topic_context(recent_topic_history(history))
        rewrite_context = await rewrite_context_prompt(self.db_path, channel, clean_text)
        if rewrite_context:
            topic_context = "\n\n".join(block for block in (topic_context, rewrite_context) if block)
        if channel == "telegram" and is_rewrite_followup(clean_text) and not await latest_rewrite_candidate(self.db_path, channel):
            result = RouteResult("What text should I rewrite?", "command", "rewrite needs target", False)
            response = await apply_reply_preferences(self.db_path, enforce_honest_claims(clean_model_text(result.response)))
            await record_route(self.db_path, input_type, result.lane, result.reason, result.cost_recorded)
            await save_history_message(self.db_path, user_id, "user", clean_text, channel)
            await save_history_message(self.db_path, user_id, "assistant", response, channel)
            return response
        await compact_if_needed(self.db_path, user_id=user_id)
        memory_context = await build_assistant_memory_context(
            db_path=self.db_path,
            memory=self.memory,
            text=clean_text,
            channel=channel,
            input_type=input_type,
            complex_route=complex_route,
            sight_route=sight_route,
        )
        skill_context = await self.skills.build_prompt_context(clean_text)
        request_text = prepare_input(channel, clean_text, memory_context, skill_context, input_type)
        self._sync_router()
        pre_route_allowed = not complex_route and not sight_route
        early_safety_response = None
        learning_response = None
        context_response = None
        if pre_route_allowed:
            try:
                early_safety_response = safety_action_reply(clean_text)
            except Exception:
                logging.exception("Early safety gate failed on channel %s", channel)
                early_safety_response = None
            try:
                learning_response = await self.learning.handle(clean_text, channel)
            except Exception:
                logging.exception("Learning pipeline failed on channel %s", channel)
                learning_response = None
            try:
                context_response = await handle_context_command(self.db_path, clean_text)
            except Exception:
                logging.exception("Context command failed on channel %s", channel)
                context_response = None
        command_response = None
        harness_response = None
        vision_response = None
        screen_response = None
        if pre_route_allowed and learning_response is None and context_response is None:
            try:
                harness_response = await self.harness.handle(clean_text, channel)
            except Exception:
                logging.exception("Harness router failed on channel %s", channel)
                harness_response = None
        if pre_route_allowed and learning_response is None and context_response is None and harness_response is None:
            try:
                command_response = await self.commands.handle(clean_text, channel)
            except Exception:
                logging.exception("Command router failed on channel %s", channel)
                if channel == "telegram" and strong_artifact_request(clean_text):
                    command_response = telegram_document_failure_reply(clean_text)
                    self.commands.last_lane = "command"
                    self.commands.last_reason = "document workflow failed before delivery"
                    self.commands.last_cost_recorded = False
                else:
                    command_response = None
        if pre_route_allowed and learning_response is None and context_response is None and harness_response is None and command_response is None:
            try:
                vision_response = await self.vision_responder.handle(clean_text, channel)
            except Exception:
                logging.exception("Vision responder failed on channel %s", channel)
                vision_response = "I had trouble using the camera just now. Try again in a bit."
            try:
                screen_response = await self.screen_responder.handle(clean_text, channel)
            except Exception:
                logging.exception("Screen responder failed on channel %s", channel)
                screen_response = "I had trouble reading the screen just now. Try /screen again in a bit."

        if early_safety_response is not None:
            result = RouteResult(early_safety_response, "command", "safety gate", False)
        elif vision_response is not None:
            cost = vision_response.startswith("I see.")
            lane = "Gemini sight" if cost else "camera sight state"
            result = RouteResult(vision_response, lane, "sight request", cost)
        elif screen_response is not None:
            cost = screen_response.startswith(("I see it.", "I see your screen."))
            lane = "Gemini screen sight" if cost else "macOS screen state"
            result = RouteResult(screen_response, lane, "screen sight request", cost)
        elif learning_response is not None:
            result = RouteResult(learning_response, "learning pipeline", "learning cue")
        elif context_response is not None:
            result = RouteResult(context_response, "command", "session context")
        elif harness_response is not None:
            result = RouteResult(
                harness_response,
                self.harness.last_lane,
                self.harness.last_reason,
                self.harness.last_cost_recorded,
            )
        elif command_response is not None:
            result = RouteResult(
                command_response,
                self.commands.last_lane or "command",
                self.commands.last_reason or "app or file action",
                self.commands.last_cost_recorded,
            )
        else:
            result = await self.router.route(
                text=clean_text,
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

        response = await apply_reply_preferences(
            self.db_path,
            enforce_telegram_truth_contract(
                enforce_honest_claims(clean_model_text(result.response)),
                result.lane,
                result.reason,
                channel,
            ),
        )
        if result.lane == "Gemini Flash text" and result.cost_recorded:
            await record_usage(self.db_path, "gemini_flash_text_calls", 1, result.reason)
        route_lane, route_reason, route_cost = route_metadata(input_type, result.lane, result.reason, result.cost_recorded)
        await self.skills.record_latest_outcome(clean_text, channel, result.lane, response)
        await record_route(self.db_path, input_type, route_lane, route_reason, route_cost)
        await save_history_message(self.db_path, user_id, "user", clean_text, channel)
        await save_history_message(self.db_path, user_id, "assistant", response, channel)
        await remember_rewrite_candidate(self.db_path, channel, clean_text, response)
        await maybe_curate_memory(self.db_path, clean_text, channel)

        if speak_reply:
            await self.voice.speak(spoken_preview(response))
        return response
