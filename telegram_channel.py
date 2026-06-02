import os
import asyncio
import logging

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

from assistant import KampungAssistant
from channel_gateway import channel_envelope
from telegram_audit import record_telegram_command
from telegram_commands import bot_commands, command_to_text, parse_command, voice_enabled
from telegram_delivery_state import last_voice_message_id, save_last_voice_message_id
from telegram_delivery import send_document_file, send_photo_file, send_speech, send_text, split_file_markers
from telegram_voice_input import transcribe_telegram_voice
from route_tracker import record_route


logger = logging.getLogger(__name__)


class TelegramChannel:
    def __init__(self, token: str, assistant: KampungAssistant):
        self.token = token
        self.assistant = assistant
        self.voice_replies = os.getenv("TELEGRAM_VOICE_REPLIES", "1") == "1"
        self.require_ara = os.getenv("TELEGRAM_REQUIRE_ARA", "1") == "1"
        self.include_text = os.getenv("TELEGRAM_VOICE_INCLUDE_TEXT", "0") == "1"
        self.delete_previous_voice = os.getenv("TELEGRAM_DELETE_PREVIOUS_VOICE", "1") == "1"

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = _update_text(update)
        if not text:
            return
        await self._handle_text(update, context, text)

    async def handle_voice_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            text = await transcribe_telegram_voice(update, context, self.assistant.db_path)
        except Exception as exc:
            logger.exception("Telegram voice note transcription failed")
            await record_route(self.assistant.db_path, "voice note", "xAI STT", f"transcription failed: {exc}", False)
            await self._send_response(
                update,
                context,
                "I could not transcribe that voice note yet. I logged it in /route.",
                input_type="voice error",
            )
            return
        if not text:
            await record_route(self.assistant.db_path, "voice note", "xAI STT", "empty transcription", False)
            await self._send_response(
                update,
                context,
                "I could not hear enough in that voice note. I logged it in /route.",
                input_type="voice error",
            )
            return
        await self._handle_text(update, context, text, input_type="voice note")

    async def handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = _update_text(update)
        if not text:
            return
        parsed = parse_command(text)
        if not parsed:
            return
        command_text = await command_to_text(self.assistant.db_path, parsed)
        result_type = "direct" if self._is_direct_command_reply(command_text) else "mapped"
        await self._record_command(update, parsed.name, parsed.args, command_text, result_type)
        if self._is_direct_command_reply(command_text):
            if parsed.name != "route":
                await record_route(self.assistant.db_path, "command", "command", f"/{parsed.name}", False)
            await self._send_response(update, context, command_text, input_type="command")
            return
        await self._handle_text(update, context, command_text, input_type="command")

    @staticmethod
    def _is_direct_command_reply(text: str) -> bool:
        return text.startswith((
            "Telegram shortcuts:",
            "Maya shortcuts:",
            "/",
            "Telegram voice replies",
            "Use /remember",
            "Use /forget",
            "Use /createskill",
            "Use /complex",
            "Usage estimate,",
            "Last route:",
            "Last artifact review:",
            "No artifact review",
            "Context window:",
            "No route recorded yet.",
            "Maya status:",
            "Memory sources:",
            "Forget result:",
            "Memory cleanup:",
            "Weekly memory status:",
            "Weekly memory run completed.",
            "Self heal check:",
            "Provider readiness:",
            "I can see now.",
            "I stopped seeing.",
            "I can see your screen now.",
            "I stopped looking at your screen.",
            "Use /screen to toggle",
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

    async def _handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, input_type: str = "text"):
        envelope = channel_envelope("telegram", text)
        response = await self.assistant.handle_text(
            str(envelope.get("text", text)),
            channel="telegram",
            speak_reply=False,
            input_type=input_type,
            channel_external_id=str(update.effective_chat.id) if update.effective_chat else "",
        )
        await self._send_response(update, context, response, input_type=input_type)

    async def _send_response(self, update: Update, context: ContextTypes.DEFAULT_TYPE, response: str, input_type: str = "text"):
        if not update.effective_chat:
            return
        chat_id = int(update.effective_chat.id)
        should_send_voice = await self._should_send_voice(input_type)
        if should_send_voice and (not self.require_ara or os.getenv("XAI_API_KEY")):
            clean_response, file_paths = split_file_markers(response)
            if self.include_text:
                await send_text(context.bot, chat_id, response)
            else:
                if _should_send_voice_text_companion(clean_response, bool(file_paths)):
                    await send_text(context.bot, chat_id, response)
                    file_paths = []
                for path in file_paths:
                    if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                        await send_photo_file(context.bot, chat_id, path, caption=path.name)
                    else:
                        await send_document_file(context.bot, chat_id, path, caption=path.name)
            await self._delete_previous_voice(context, chat_id)
            sent_message = await send_speech(
                context.bot,
                chat_id,
                self.assistant.voice,
                _voice_companion_text(clean_response),
            )
            message_id = getattr(sent_message, "message_id", None)
            if message_id:
                await save_last_voice_message_id(self.assistant.db_path, chat_id, int(message_id))
            return
        await send_text(context.bot, chat_id, response)

    async def _delete_previous_voice(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
        if not self.delete_previous_voice:
            return
        message_id = await last_voice_message_id(self.assistant.db_path, chat_id)
        if not message_id:
            return
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception as exc:
            logger.info("Could not delete previous Telegram voice message %s: %s", message_id, exc)

    async def _should_send_voice(self, input_type: str) -> bool:
        if input_type == "voice note":
            return self.voice_replies or await voice_enabled(self.assistant.db_path)
        if input_type == "command":
            return False
        return False

    async def run(self):
        app = (
            ApplicationBuilder()
            .token(self.token)
            .read_timeout(_timeout_env("TELEGRAM_READ_TIMEOUT", 30.0))
            .write_timeout(_timeout_env("TELEGRAM_WRITE_TIMEOUT", 30.0))
            .media_write_timeout(_timeout_env("TELEGRAM_MEDIA_WRITE_TIMEOUT", 180.0))
            .connect_timeout(_timeout_env("TELEGRAM_CONNECT_TIMEOUT", 20.0))
            .pool_timeout(_timeout_env("TELEGRAM_POOL_TIMEOUT", 20.0))
            .build()
        )
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


def _update_text(update: Update) -> str:
    message = update.effective_message
    if not message or not message.text:
        return ""
    return message.text.strip()


def _should_send_voice_text_companion(text: str, has_files: bool) -> bool:
    if has_files:
        return True
    lowered = text.lower()
    return "/users/" in lowered or "path:" in lowered or "last document:" in lowered


def _voice_companion_text(text: str) -> str:
    summary = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("summary:"):
            summary = stripped.split(":", 1)[1].strip()
            break
        if stripped.lower().startswith("3) summary:"):
            summary = stripped.split(":", 1)[1].strip()
            break
    if summary:
        return summary
    cleaned_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if "/users/" in lowered or lowered.startswith(("last document:", "1) path:", "path:")):
            continue
        if stripped:
            cleaned_lines.append(stripped)
    return "\n".join(cleaned_lines).strip() or "I sent the file details in text."


def _timeout_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default
