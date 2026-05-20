import os
import asyncio
import logging

from agent_runtime import AgentRuntime
from assistant import KampungAssistant
from camera_adapter import ExternalCameraAdapter
from config import require_env
from context_layers import init_context_layers_db
from health_monitor import HealthReporter
from harness_idempotency import init_action_ledger
from harness_store import init_harness_db
from harness_artifact_store import init_harness_artifact_db
from harness_observation_store import init_harness_observation_db
from hardware_event_store import init_hardware_event_db
from lesson_store import init_lesson_db
from logging_setup import configure_logging
from local_voice_channel import LocalVoiceChannel
from mudra_adapter import MudraAdapter
from routine_store import init_routine_db
from route_tracker import init_route_db
from session_memory_store import init_session_memory_db
from self_heal_store import init_self_heal_db
from sieve import SieveNode
from skill_store import init_skill_db
from skill_learning_store import init_skill_learning_db
from storage import init_db
from telegram_channel import TelegramChannel
from weekly_memory_store import init_weekly_memory_db
from workflow_store import init_workflow_db


async def main():
    configure_logging()
    logger = logging.getLogger("maya.main")
    require_env(["GOOGLE_API_KEY", "KIMI_API_KEY"])
    db_path = os.getenv("KAMPUNG_DB_PATH", "session_history.db")
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_skill_learning_db(db_path)
    await init_routine_db(db_path)
    await init_route_db(db_path)
    await init_weekly_memory_db(db_path)
    await init_session_memory_db(db_path)
    await init_context_layers_db(db_path)
    await init_workflow_db(db_path)
    await init_self_heal_db(db_path)
    await init_harness_db(db_path)
    await init_action_ledger(db_path)
    await init_harness_artifact_db(db_path)
    await init_harness_observation_db(db_path)
    await init_hardware_event_db(db_path)

    assistant = KampungAssistant(db_path=db_path)
    tasks = [asyncio.create_task(HealthReporter(db_path=db_path).run())]

    if os.getenv("ENABLE_AGENT_RUNTIME", "1") == "1":
        tasks.append(asyncio.create_task(AgentRuntime(db_path=db_path).run()))

    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if telegram_token:
        tasks.append(asyncio.create_task(TelegramChannel(telegram_token, assistant).run()))

    if os.getenv("ENABLE_IMAC_CHANNEL", "0") == "1":
        tasks.append(asyncio.create_task(LocalVoiceChannel(assistant).run()))

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

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down.")
