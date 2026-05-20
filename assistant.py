import logging, os

from assistant_context_helpers import handle_context_command
from assistant_text import clean_model_text, normalize_history, strip_wake_prefix
from assistant_commands import AssistantCommandRouter
from learning_pipeline import LearningPipeline
from assistant_model_lanes import ModelLanes
from assistant_reply_paths import prepare_input
from assistant_routes import AssistantRouter, RouteResult
from harness_router import HarnessRouter
from memory_service import MemoryService
from models import TheSenses
from orchestrator import Orchestrator
from quantum_advisory import quantum_context_hint
from project_store import build_project_context
from response_policy import ResponsePolicy
from response_style import apply_reply_preferences
from route_tracker import record_route
from screen_responder import ScreenResponder
from session_compactor import build_session_context, compact_if_needed
from skill_registry import SkillRegistry
from storage import get_history, save_history_message
from topic_context import format_topic_context, recent_topic_history
from voice import VoiceNode, spoken_preview
from vision_responder import VisionResponder

PRIMARY_USER_ID = 1
COMPLEX_ROUTE_PREFIX = "[complex]"
SIGHT_ROUTE_PREFIX = "[sight]"

class KampungAssistant:
    def __init__(self, db_path: str = "session_history.db"):
        self.db_path = db_path
        self.orchestrator = Orchestrator(db_path=db_path)
        self.memory = MemoryService(db_path)
        self.skills = SkillRegistry(db_path)
        self.commands = AssistantCommandRouter(db_path, self.memory, self.skills)
        self.policy = ResponsePolicy()
        self.learning = LearningPipeline(db_path)
        self.vision_responder = VisionResponder(db_path)
        self.screen_responder = ScreenResponder(db_path)
        self.harness = HarnessRouter(db_path)
        self.model_lanes = ModelLanes(db_path)
        self.imac_fast_responder = self.model_lanes.build_imac_fast_responder()
        self.telegram_fast_responder = TheSenses(os.getenv("GOOGLE_API_KEY", "dummy"))
        self.router = AssistantRouter(
            commands=self.commands,
            learning=self.learning,
            policy=self.policy,
            model_lanes=self.model_lanes,
            orchestrator=self.orchestrator,
            telegram_fast_responder=self.telegram_fast_responder,
            imac_fast_responder=self.imac_fast_responder,
        )
        self.voice = VoiceNode(db_path)

    @staticmethod
    def _is_complex_route(text: str) -> bool:
        return text.lower().startswith(COMPLEX_ROUTE_PREFIX)
    @staticmethod
    def _is_sight_route(text: str) -> bool:
        return text.lower().startswith(SIGHT_ROUTE_PREFIX)
    @staticmethod
    def _complex_payload(text: str) -> str:
        return text[len(COMPLEX_ROUTE_PREFIX):].strip()
    @staticmethod
    def _sight_payload(text: str) -> str:
        return text[len(SIGHT_ROUTE_PREFIX):].strip()
    @staticmethod
    def spoken_preview(text: str) -> str:
        return spoken_preview(text)

    def _sync_router(self) -> None:
        self.router.commands = self.commands
        self.router.learning = self.learning
        self.router.policy = self.policy
        self.router.model_lanes = self.model_lanes
        self.router.orchestrator = self.orchestrator
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
    ) -> str:
        clean_text = strip_wake_prefix(text)
        if not clean_text:
            return "Send me something real and I'll take it from there."

        complex_route = self._is_complex_route(clean_text)
        sight_route = self._is_sight_route(clean_text)
        if complex_route:
            clean_text = self._complex_payload(clean_text)
            if not clean_text:
                return "Use /complex followed by the question or decision you want me to think through."
        if sight_route:
            clean_text = self._sight_payload(clean_text)
            if not clean_text:
                return "Tell me what you want me to think through."

        history = normalize_history(await get_history(self.db_path, user_id))
        topic_history = recent_topic_history(history)
        topic_context = format_topic_context(topic_history)
        await compact_if_needed(self.db_path, user_id=user_id)
        base_memory_context = await self.memory.build_prompt_context(clean_text)
        session_context = await build_session_context(self.db_path, clean_text)
        quantum_context = await quantum_context_hint(self.db_path, clean_text)
        project_context = await build_project_context(self.db_path, clean_text)
        memory_context = "\n\n".join(
            block for block in (project_context, session_context, quantum_context, base_memory_context) if block
        )
        skill_context = await self.skills.build_prompt_context(clean_text)
        request_text = prepare_input(channel, clean_text, memory_context, skill_context)
        self._sync_router()
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
        if learning_response is None and context_response is None:
            try:
                harness_response = await self.harness.handle(clean_text, channel)
            except Exception:
                logging.exception("Harness router failed on channel %s", channel)
                harness_response = None
        if learning_response is None and context_response is None and harness_response is None:
            try:
                command_response = await self.commands.handle(clean_text, channel)
            except Exception:
                logging.exception("Command router failed on channel %s", channel)
                command_response = None
        if learning_response is None and context_response is None and harness_response is None and command_response is None:
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

        if vision_response is not None:
            result = RouteResult(vision_response, "Gemini sight", "sight request", "I see." in vision_response)
        elif screen_response is not None:
            cost = screen_response.startswith(("I see it.", "I see your screen."))
            lane = "Gemini screen sight" if cost else "macOS screen state"
            result = RouteResult(screen_response, lane, "screen sight request", cost)
        elif learning_response is not None:
            result = RouteResult(learning_response, "learning pipeline", "learning cue")
        elif context_response is not None:
            result = RouteResult(context_response, "command", "session context")
        elif harness_response is not None:
            result = RouteResult(harness_response, "LangGraph harness", "persistent workflow")
        elif command_response is not None:
            result = RouteResult(command_response, "command", "app or file action")
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
            )

        response = await apply_reply_preferences(self.db_path, clean_model_text(result.response))
        await record_route(self.db_path, input_type, result.lane, result.reason, result.cost_recorded)
        await save_history_message(self.db_path, user_id, "user", clean_text)
        await save_history_message(self.db_path, user_id, "assistant", response)

        if speak_reply:
            await self.voice.speak(spoken_preview(response))
        return response
