import os
import asyncio
import logging

from maya_core.agent_runtime import AgentRuntime
from maya_core.assistant import KampungAssistant
from maya_documents.artifact_review_store import init_artifact_review_db
from maya_core.camera_adapter import ExternalCameraAdapter
from maya_core.config import require_env
from maya_core.context_layers import init_context_layers_db
from maya_core.curated_memory import init_curated_memory_db
from maya_core.health_monitor import HealthReporter
from maya_harness.harness_idempotency import init_action_ledger
from maya_harness.harness_store import init_harness_db
from maya_harness.harness_artifact_store import init_harness_artifact_db
from maya_harness.harness_observation_store import init_harness_observation_db
from maya_core.hotkey_voice_channel import HotkeyVoiceChannel
from maya_core.hardware_event_store import init_hardware_event_db
from maya_core.lesson_store import init_lesson_db
from maya_core.logging_setup import configure_logging
from maya_core.local_voice_channel import LocalVoiceChannel
from maya_browser.bridge_runtime import BrowserBridgeMonitor, warm_browser_bridge_once
from maya_core.maya_engine_lock import acquire_engine_lock
from maya_core.mudra_adapter import MudraAdapter
from routine_store import init_routine_db
from route_tracker import init_route_db
from session_memory_store import init_session_memory_db
from session_search import init_session_search_db
from self_heal_store import init_self_heal_db
from sieve import SieveNode
from skill_store import init_skill_db
from skill_learning_store import init_skill_learning_db
from skill_memory_store import init_skill_memory_db
from skill_outcome_store import init_skill_outcome_db
from storage import init_db
from telegram_channel import TelegramChannel
from weekly_memory_store import init_weekly_memory_db
from weekly_skill_review import init_skill_review_db
from user_model_store import init_user_model_db
from workflow_store import init_workflow_db
from xai_voice_work import init_voice_work_db


async def _supervise(name: str, factory, delay_seconds: float = 5.0):
    logger = logging.getLogger("maya.supervisor")
    while True:
        try:
            await factory()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("%s task crashed; restarting in %.1fs", name, delay_seconds)
            await asyncio.sleep(delay_seconds)


async def main():
    configure_logging()
    logger = logging.getLogger("maya.main")
    engine_lock = acquire_engine_lock()
    if engine_lock is None:
        return
    try:
        require_env(["GOOGLE_API_KEY"])
        db_path = os.getenv("KAMPUNG_DB_PATH", "session_history.db")
        await init_db(db_path)
        await init_lesson_db(db_path)
        await init_skill_db(db_path)
        await init_skill_learning_db(db_path)
        await init_skill_memory_db(db_path)
        await init_skill_outcome_db(db_path)
        await init_skill_review_db(db_path)
        await init_user_model_db(db_path)
        await init_routine_db(db_path)
        await init_route_db(db_path)
        await init_weekly_memory_db(db_path)
        await init_session_memory_db(db_path)
        await init_session_search_db(db_path)
        await init_curated_memory_db(db_path)
        await init_context_layers_db(db_path)
        await init_workflow_db(db_path)
        await init_voice_work_db(db_path)
        await init_artifact_review_db(db_path)
        await init_self_heal_db(db_path)
        await init_harness_db(db_path)
        await init_action_ledger(db_path)
        await init_harness_artifact_db(db_path)
        await init_harness_observation_db(db_path)
        await init_hardware_event_db(db_path)

        assistant = KampungAssistant(db_path=db_path)
        tasks = [asyncio.create_task(HealthReporter(db_path=db_path).run())]

        if os.getenv("MAYA_BROWSER_BRIDGE_WARMUP", "1") != "0":
            await warm_browser_bridge_once()
            tasks.append(asyncio.create_task(_supervise("browser_bridge", lambda: BrowserBridgeMonitor().run())))

        if os.getenv("ENABLE_AGENT_RUNTIME", "1") == "1":
            tasks.append(asyncio.create_task(_supervise("agent_runtime", lambda: AgentRuntime(db_path=db_path).run())))

        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if telegram_token:
            tasks.append(asyncio.create_task(_supervise("telegram", lambda: TelegramChannel(telegram_token, assistant).run())))

        if os.getenv("ENABLE_IMAC_CHANNEL", "0") == "1":
            tasks.append(asyncio.create_task(LocalVoiceChannel(assistant).run()))

        if os.getenv("ENABLE_IMAC_HOTKEY_CHANNEL", "0") == "1":
            tasks.append(asyncio.create_task(_supervise("hotkey_voice", lambda: HotkeyVoiceChannel(assistant).run())))

        if os.getenv("ENABLE_OMI_ADAPTER", "0") == "1":
            watch_dir = os.getenv("OMI_WATCH_DIR", "omi_sync")
            tasks.append(asyncio.create_task(SieveNode(watch_dir, db_path).run()))

        if os.getenv("ENABLE_MUDRA_ADAPTER", "0") == "1":
            event_dir = os.getenv("MUDRA_EVENT_DIR", "mudra_sync")
            tasks.append(asyncio.create_task(MudraAdapter(assistant, event_dir).run()))

        if os.getenv("ENABLE_EXTERNAL_CAMERA_ADAPTER", "0") == "1":
            event_dir = os.getenv("EXTERNAL_CAMERA_EVENT_DIR", "camera_sync")
            tasks.append(asyncio.create_task(ExternalCameraAdapter(assistant, event_dir).run()))

        if len(tasks) == 1:
            raise ValueError("No channels enabled. Configure Telegram or ENABLE_IMAC_CHANNEL=1.")

        logger.info("Kampung AI runtime starting.")
        await asyncio.gather(*tasks)
    finally:
        engine_lock.release()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down.")
