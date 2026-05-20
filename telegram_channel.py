import os
import asyncio

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

from assistant import KampungAssistant
from storage import upsert_preference
from telegram_audit import record_telegram_command
from telegram_commands import bot_commands, command_to_text, parse_command, voice_enabled
from telegram_delivery import send_speech, send_text
from telegram_voice_input import transcribe_telegram_voice
from route_tracker import record_route


class TelegramChannel:
    def __init__(self, token: str, assistant: KampungAssistant):
        self.token = token
        self.assistant = assistant
        self.voice_replies = os.getenv("TELEGRAM_VOICE_REPLIES", "1") == "1"
        self.require_ara = os.getenv("TELEGRAM_REQUIRE_ARA", "1") == "1"
        self.include_text = os.getenv("TELEGRAM_VOICE_INCLUDE_TEXT", "1") == "1"

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (update.message.text or "").strip()
        await self._handle_text(update, context, text)

    async def handle_voice_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            text = await transcribe_telegram_voice(update, context, self.assistant.db_path)
        except Exception:
            await self._send_response(update, context, "I could not transcribe that voice note yet.")
            return
        if not text:
            await self._send_response(update, context, "I could not hear enough in that voice note.")
            return
        await self._handle_text(update, context, text, input_type="voice note")

    async def handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (update.message.text or "").strip()
        parsed = parse_command(text)
        if not parsed:
            return
        command_text = await command_to_text(self.assistant.db_path, parsed)
        result_type = "direct" if self._is_direct_command_reply(command_text) else "mapped"
        await self._record_command(update, parsed.name, parsed.args, command_text, result_type)
        await self._record_route_command(parsed.name, result_type)
        if self._is_direct_command_reply(command_text):
            await self._send_response(update, context, command_text)
            return
        await self._handle_text(update, context, command_text, input_type="command")

    @staticmethod
    def _is_direct_command_reply(text: str) -> bool:
        return text.startswith((
            "Telegram shortcuts:",
            "Maya shortcuts:",
            "Telegram voice replies",
            "Use /remember",
            "Use /forget",
            "Use /createskill",
            "Use /complex",
            "Usage estimate,",
            "Last route:",
            "Context window:",
            "No route recorded yet.",
            "Maya status:",
            "Memory sources:",
            "Forget result:",
            "Memory cleanup:",
            "Self heal check:",
            "Provider readiness:",
            "I can see now.",
            "I can see your screen now.",
            "I stopped looking at your screen.",
            "I could not open the local camera preview.",
            "Local camera preview is disabled.",
        ))

    async def _record_command(self, update: Update, command: str, args: str, mapped_text: str, result_type: str):
        chat_id = str(update.effective_chat.id) if update.effective_chat else ""
        await record_telegram_command(
            self.assistant.db_path,
            chat_id=chat_id,
            command=command,
            args=args,
            mapped_text=mapped_text,
            result_type=result_type,
        )

    async def _record_route_command(self, command: str, result_type: str) -> None:
        if command == "route":
            return
        if result_type == "direct":
            await record_route(self.assistant.db_path, "command", "command", f"/{command}", False)

    async def _handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, input_type: str = "text"):
        if update.effective_chat:
            await upsert_preference(
                self.assistant.db_path,
                key="telegram_chat_id",
                value=str(update.effective_chat.id),
                source="telegram",
            )
        response = await self.assistant.handle_text(
            text,
            channel="telegram",
            speak_reply=False,
            input_type=input_type,
        )
        await self._send_response(update, context, response)

    async def _send_response(self, update: Update, context: ContextTypes.DEFAULT_TYPE, response: str):
        if not update.effective_chat:
            return
        chat_id = int(update.effective_chat.id)
        should_send_voice = self.voice_replies or await voice_enabled(self.assistant.db_path)
        if should_send_voice and (not self.require_ara or os.getenv("XAI_API_KEY")):
            if self.include_text:
                await send_text(context.bot, chat_id, response)
            await send_speech(
                context.bot,
                chat_id,
                self.assistant.voice,
                self.assistant.spoken_preview(response),
            )
            return
        await send_text(context.bot, chat_id, response)

    async def run(self):
        app = ApplicationBuilder().token(self.token).build()
        app.add_handler(MessageHandler(filters.COMMAND, self.handle_command))
        app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, self.handle_voice_message))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message))

        print("Telegram channel is live.")
        await app.initialize()
        await app.bot.set_my_commands(bot_commands())
        if app.updater:
            await app.updater.start_polling()
        await app.start()
        await context_forever()


async def context_forever():
    while True:
        await asyncio.sleep(1)
