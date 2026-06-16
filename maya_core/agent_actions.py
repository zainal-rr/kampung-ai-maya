from __future__ import annotations

import asyncio
import os

from telegram import Bot

from maya_core.briefing_service import BriefingBuilder
from delivery_redaction import redact_for_delivery
from skill_factory import SkillFactory
from storage import get_history, get_preference, list_tasks
from telegram_delivery import send_speech, send_text
from utils import OSBridge
from voice import VoiceNode


class AgentActionExecutor:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.bridge = OSBridge()
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.briefings = BriefingBuilder(db_path)
        self.skill_factory = SkillFactory(db_path)
        self.voice = VoiceNode(db_path)

    async def execute_step(
        self,
        task: dict[str, str | int | None],
        step_name: str,
        context: dict[str, str | bool],
    ) -> dict[str, str | bool]:
        if step_name == "prepare_message":
            return await self._prepare_follow_up(task, context)
        if step_name == "collect_summary":
            return await self._collect_summary(context)
        if step_name == "deliver_message":
            return await self._deliver_message(task, context)
        if step_name == "queue_digest":
            context["queued"] = True
            context["result"] = "Queued Omi digest review for Gemini memory shaping."
            return context
        if step_name == "scaffold_skill":
            return await self._scaffold_skill(task, context)
        raise ValueError(f"Unsupported plan step: {step_name}")

    async def _prepare_follow_up(self, task, context):
        if str(task["action_type"]) == "send_message":
            return await self._prepare_send_message(task, context)
        if str(task["action_type"]) == "scheduled_briefing":
            return await self._prepare_briefing(task, context)
        title = str(task["title"])
        details = str(task.get("details") or "")
        context["message"] = details or title
        context["result"] = f"Prepared follow-up for task #{task['id']}: {title}"
        return context

    async def _collect_summary(self, context):
        history = await get_history(self.db_path, user_id=1, limit=6)
        lines = [f"{item['role']}: {item['content'][:90]}" for item in history if item["content"].strip()]
        summary = " | ".join(lines) if lines else "No recent history available."
        context["message"] = summary[:240]
        context["result"] = f"Prepared short history summary: {summary[:200]}"
        return context

    async def _prepare_send_message(self, task, context):
        payload = str(task.get("payload") or "")
        destination, raw_payload = self._split_delivery_payload(payload)
        context["delivery_channel"] = destination

        if raw_payload == "task_list":
            tasks = await list_tasks(self.db_path, limit=5)
            lines = [f"#{item['id']} {item['title']} ({item['status']})" for item in tasks]
            message = "Open tasks:\n" + "\n".join(lines) if lines else "You don't have any open tasks right now."
        elif raw_payload == "history_summary":
            history = await get_history(self.db_path, user_id=1, limit=6)
            lines = [f"{item['role']}: {item['content'][:90]}" for item in history if item["content"].strip()]
            message = "Recent summary:\n" + (" | ".join(lines) if lines else "No recent history available.")
        elif raw_payload.startswith("literal:"):
            message = raw_payload.split(":", 1)[1].strip()
        else:
            message = str(task["title"])

        context["message"] = message
        context["result"] = f"Prepared outbound message for task #{task['id']}."
        return context

    async def _prepare_briefing(self, task, context):
        channel = str(task.get("channel") or "imac")
        kind = str(task.get("payload") or "morning_briefing")
        message = await self.briefings.build(kind, channel)
        context["message"] = message
        context["result"] = f"Prepared {kind.replace('_', ' ')} for task #{task['id']}."
        return context

    async def _deliver_message(self, task, context):
        channel = str(context.get("delivery_channel") or task.get("channel") or "imac")
        title = "Maya Reminder" if str(task["action_type"]) == "follow_up" else "Maya Summary"
        if str(task["action_type"]) == "scheduled_briefing":
            title = "Maya Briefing"
        message = str(context.get("message") or task.get("title") or "").strip()
        message = redact_for_delivery(message, channel)
        if channel == "telegram":
            await self._send_telegram(message, task)
        elif str(task["action_type"]) == "scheduled_briefing":
            await self.voice.speak(message)
        else:
            await asyncio.to_thread(self.bridge.notify, title, message)
        context["delivered"] = True
        context["result"] = f"Delivered task #{task['id']} via {channel}."
        return context

    async def _scaffold_skill(self, task, context):
        payload = str(task.get("payload") or task.get("details") or task.get("title") or "")
        result = await self.skill_factory.scaffold_skill(payload)
        context["scaffold_path"] = result["scaffold_path"]
        context["result"] = (
            f"Created draft skill '{result['title']}' "
            f"at {result['scaffold_path']} with proposal #{result['proposal_id']}."
        )
        return context

    async def _send_telegram(self, message: str, task) -> None:
        chat_id = await get_preference(self.db_path, "telegram_chat_id")
        if not self.telegram_token or not chat_id:
            raise RuntimeError("Telegram delivery is not ready yet. No token or chat id is stored.")
        bot = Bot(token=self.telegram_token)
        should_send_audio = (
            os.getenv("TELEGRAM_ROUTINE_AUDIO", "0") == "1"
            and str(task.get("action_type")) == "scheduled_briefing"
        )
        if should_send_audio:
            if os.getenv("TELEGRAM_VOICE_INCLUDE_TEXT", "1") == "1":
                await send_text(bot, int(chat_id), message)
            await send_speech(bot, int(chat_id), self.voice, message)
            return
        await send_text(bot, int(chat_id), message)

    @staticmethod
    def _split_delivery_payload(payload: str) -> tuple[str, str]:
        if "|" not in payload:
            return "imac", payload
        destination, content = payload.split("|", 1)
        return destination, content
