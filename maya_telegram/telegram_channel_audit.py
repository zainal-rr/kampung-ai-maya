from __future__ import annotations

import logging
import time

from telegram import Update

from telegram_delivery_log import record_telegram_delivery
from telegram_turn_log import record_telegram_turn

logger = logging.getLogger(__name__)


async def record_delivery_event(
    db_path: str,
    *,
    chat_id: int,
    input_type: str,
    response: str,
    events: list[dict[str, str]],
) -> None:
    status = "failed" if any(item.get("status") == "failed" for item in events) else "sent"
    try:
        await record_telegram_delivery(
            db_path,
            chat_id=chat_id,
            input_type=input_type,
            status=status,
            text_chars=len(response),
            files=[item for item in events if item.get("kind") in {"document", "photo", "file"}],
            error="; ".join(item.get("error", "") for item in events if item.get("error")),
        )
    except Exception:
        logger.exception("Could not record Telegram delivery event")


async def record_turn_event(
    db_path: str,
    update: Update,
    *,
    input_type: str,
    prompt: str,
    status: str,
    started: float,
    response_chars: int,
    response_preview: str = "",
    error: str = "",
) -> None:
    if not update.effective_chat:
        return
    try:
        await record_telegram_turn(
            db_path,
            chat_id=int(update.effective_chat.id),
            input_type=input_type,
            prompt=prompt,
            status=status,
            duration_ms=int((time.monotonic() - started) * 1000),
            response_chars=response_chars,
            response_preview=response_preview,
            error=error,
        )
    except Exception:
        logger.exception("Could not record Telegram turn event")
