"""Telegram transport adapter for Maya's shared assistant runtime.

This module should stay thin. It receives Telegram text, voice notes, and photos;
normalizes them into Maya channel envelopes; calls `KampungAssistant`; records
turn/route/delivery audit events; and sends text, voice, photos, or document
attachments back to Telegram.

Do not put document semantics here. Voice notes become text through xAI STT, then
the same artifact routers handle them as ordinary Telegram turns. That is what
keeps phone voice, Telegram text, and iMac voice aligned after transcription.
"""

import os
import asyncio
import logging
import time

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

from maya_core.assistant import KampungAssistant
from maya_core.channel_gateway import channel_envelope
from telegram_audit import record_telegram_command
from telegram_channel_audit import record_delivery_event, record_turn_event
from telegram_command_direct import is_direct_command_reply
from telegram_commands import bot_commands, command_to_text, parse_command, voice_enabled
from telegram_delivery_state import last_voice_message_id, save_last_voice_message_id
from telegram_poller_lock import acquire_poller_lock
from telegram_turn_log import finalize_telegram_turn, record_telegram_turn_received
from telegram_delivery import send_document_file, send_photo_file, send_speech, send_text, split_file_markers
from telegram_photo_input import describe_telegram_photo
from telegram_voice_input import transcribe_telegram_voice
from route_tracker import record_route
from maya_core.maya_runtime_config import runtime_config


logger = logging.getLogger(__name__)


class TelegramChannel:
    def __init__(self, token: str, assistant: KampungAssistant):
        self.token = token
        self.assistant = assistant
        self.voice_replies = os.getenv("TELEGRAM_VOICE_REPLIES", "1") == "1"
        self.require_ara = os.getenv("TELEGRAM_REQUIRE_ARA", "1") == "1"
        self.include_text = os.getenv("TELEGRAM_VOICE_INCLUDE_TEXT", "0") == "1"
        self.delete_previous_voice = os.getenv("TELEGRAM_DELETE_PREVIOUS_VOICE", "1") == "1"
        self.allowed_chat_ids = set(runtime_config().telegram_allowed_chat_ids)

    def _authorized(self, update: Update) -> bool:
        """Closed by default: only chat ids in TELEGRAM_ALLOWED_CHAT_IDS may talk to Maya."""
        chat = update.effective_chat
        if chat is None:
            return False
        if not self.allowed_chat_ids:
            logger.warning(
                "Rejected Telegram chat %s: TELEGRAM_ALLOWED_CHAT_IDS is not set.", chat.id
            )
            return False
        if str(chat.id) in self.allowed_chat_ids:
            return True
        logger.warning("Rejected unauthorized Telegram chat %s.", chat.id)
        return False

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update):
            return
        text = _update_text(update)
        if not text:
            return
        await self._handle_text(update, context, text)

    async def handle_voice_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update):
            return
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

    async def handle_photo_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update):
            return
        started = time.monotonic()
        caption = (getattr(update.effective_message, "caption", "") or "").strip()
        prompt = caption or "[Telegram photo]"
        try:
            response = await describe_telegram_photo(update, context, self.assistant.db_path)
            if not response:
                await record_route(self.assistant.db_path, "photo", "Gemini Flash sight", "empty Telegram photo", False)
                response = "I could not read that photo yet. Try sending it again with a short caption."
            else:
                await record_route(self.assistant.db_path, "photo", "Gemini Flash sight", "Telegram photo", True)
            await self._send_response(update, context, response, input_type="photo")
            await self._record_turn(update, "photo", prompt, "completed", started, len(response), response=response)
        except Exception as exc:
            logger.exception("Telegram photo handling failed")
            await record_route(self.assistant.db_path, "photo", "Gemini Flash sight", f"photo failed: {exc}", False)
            response = "I could not read that photo yet. I logged it in /route."
            await self._send_response(update, context, response, input_type="photo error")
            await self._record_turn(update, "photo", prompt, "failed", started, 0, exc.__class__.__name__)

    async def handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update):
            return
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
            started = time.monotonic()
            await self._send_response(update, context, command_text, input_type="command")
            await self._record_turn(update, "command", text, "completed", started, len(command_text), response=command_text)
            return
        await self._handle_text(update, context, command_text, input_type="command")

    @staticmethod
    def _is_direct_command_reply(text: str) -> bool:
        return is_direct_command_reply(text)

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
        started = time.monotonic()
        envelope = channel_envelope("telegram", text)
        prompt = str(envelope.get("text", text))
        chat_id = str(update.effective_chat.id) if update.effective_chat else ""
        # Durable intake guard: record the turn BEFORE any processing so a
        # crash or task cancellation mid-handling leaves a visible orphaned
        # 'received' row instead of a silently vanished message
        # (live incident 2026-06-10: skill_usage rows existed, turn rows did not).
        turn_id: int | None = None
        try:
            turn_id = await record_telegram_turn_received(
                self.assistant.db_path, chat_id=chat_id, input_type=input_type, prompt=prompt
            )
        except Exception:
            logger.exception("Could not record received Telegram turn")
        try:
            response = await self.assistant.handle_text(
                prompt,
                channel="telegram",
                speak_reply=False,
                input_type=input_type,
                channel_external_id=chat_id,
            )
            await self._send_response(update, context, response, input_type=input_type)
            await self._finalize_turn(turn_id, update, input_type, prompt, "completed", started, len(response), response=response)
        except BaseException as exc:
            # BaseException on purpose: asyncio.CancelledError does NOT inherit
            # from Exception, so a poller conflict cancelling this task used to
            # skip turn recording entirely. The finalize write is shielded so
            # it completes even while this task is being cancelled.
            await self._finalize_turn(turn_id, update, input_type, prompt, "failed", started, 0, error=exc.__class__.__name__)
            raise

    async def _finalize_turn(
        self,
        turn_id: int | None,
        update: Update,
        input_type: str,
        prompt: str,
        status: str,
        started: float,
        response_chars: int,
        response: str = "",
        error: str = "",
    ) -> None:
        try:
            if turn_id is not None:
                await asyncio.shield(
                    finalize_telegram_turn(
                        self.assistant.db_path,
                        turn_id,
                        status=status,
                        duration_ms=int((time.monotonic() - started) * 1000),
                        response_chars=response_chars,
                        response_preview=response[:1000],
                        error=error,
                    )
                )
            else:
                await asyncio.shield(
                    record_turn_event(
                        self.assistant.db_path,
                        update,
                        input_type=input_type,
                        prompt=prompt,
                        status=status,
                        started=started,
                        response_chars=response_chars,
                        response_preview=response,
                        error=error,
                    )
                )
        except BaseException:
            logger.exception("Could not finalize Telegram turn %s", turn_id)

    async def _send_response(self, update: Update, context: ContextTypes.DEFAULT_TYPE, response: str, input_type: str = "text"):
        if not update.effective_chat:
            return
        chat_id = int(update.effective_chat.id)
        should_send_voice = await self._should_send_voice(input_type)
        if should_send_voice and (not self.require_ara or os.getenv("XAI_API_KEY")):
            clean_response, file_paths = split_file_markers(response)
            delivery_events = []
            if self.include_text:
                delivery_events = await send_text(context.bot, chat_id, response)
            else:
                if _should_send_voice_text_companion(clean_response, bool(file_paths)):
                    delivery_events = await send_text(context.bot, chat_id, response)
                    file_paths = []
                for path in file_paths:
                    if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                        await send_photo_file(context.bot, chat_id, path, caption=path.name)
                        delivery_events.append({"kind": "photo", "status": "sent", "path": str(path)})
                    else:
                        await send_document_file(context.bot, chat_id, path, caption=path.name)
                        delivery_events.append({"kind": "document", "status": "sent", "path": str(path)})
            await self._record_delivery(chat_id, input_type, response, delivery_events)
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
        delivery_events = await send_text(context.bot, chat_id, response)
        await self._record_delivery(chat_id, input_type, response, delivery_events)

    async def _record_delivery(self, chat_id: int, input_type: str, response: str, events: list[dict[str, str]]) -> None:
        await record_delivery_event(self.assistant.db_path, chat_id=chat_id, input_type=input_type, response=response, events=events)

    async def _record_turn(
        self,
        update: Update,
        input_type: str,
        prompt: str,
        status: str,
        started: float,
        response_chars: int,
        error: str = "",
        response: str = "",
    ) -> None:
        await record_turn_event(
            self.assistant.db_path,
            update,
            input_type=input_type,
            prompt=prompt,
            status=status,
            started=started,
            response_chars=response_chars,
            response_preview=response,
            error=error,
        )

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
        if input_type != "voice note":
            return False
        return self.voice_replies or await voice_enabled(self.assistant.db_path)

    async def run(self):
        # Single-poller guarantee: a second getUpdates loop on the same token
        # makes Telegram terminate connections (telegram.error.Conflict) and
        # silently drops in-flight turns. Refuse to double-poll.
        lock = acquire_poller_lock("telegram")
        if lock is None:
            retry_seconds = _timeout_env("MAYA_TELEGRAM_POLLER_RETRY_SECONDS", 30.0)
            logger.critical(
                "Another Telegram poller holds the lock; not starting a second one. Retrying in %.0fs.",
                retry_seconds,
            )
            await asyncio.sleep(retry_seconds)
            return
        try:
            await self._run_polling()
        finally:
            lock.release()

    async def _run_polling(self):
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
        app.add_handler(MessageHandler(filters.PHOTO, self.handle_photo_message))
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
