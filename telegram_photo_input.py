from __future__ import annotations

import os
import tempfile
from pathlib import Path

from cost_tracker import record_usage
from language_policy import language_instruction
from models import TheSenses


async def describe_telegram_photo(update, context, db_path: str, *, senses=None) -> str:
    message = getattr(update, "effective_message", None) or getattr(update, "message", None)
    photos = list(getattr(message, "photo", None) or [])
    if not photos:
        return ""
    photo = photos[-1]
    caption = (getattr(message, "caption", "") or "").strip()
    image_bytes = await _download_photo_bytes(context, getattr(photo, "file_id", ""))
    observer = senses or TheSenses(os.getenv("GOOGLE_API_KEY", "dummy"), os.getenv("GEMINI_FLASH_MODEL", "gemini-3.1-flash"))
    answer = (await observer.describe_image(image_bytes, _photo_prompt(caption))).strip()
    await record_usage(db_path, "gemini_flash_vision_calls", 1, "telegram photo")
    return answer or "I can see the photo, but I could not describe it clearly. Send a clearer image or add a caption."


async def _download_photo_bytes(context, file_id: str) -> bytes:
    telegram_file = await context.bot.get_file(file_id)
    with tempfile.TemporaryDirectory(prefix="maya-telegram-photo-") as tmp:
        path = Path(tmp) / "telegram_photo.jpg"
        await telegram_file.download_to_drive(custom_path=str(path))
        return path.read_bytes()


def _photo_prompt(caption: str) -> str:
    request = caption or "Describe this photo and say what you can help with next."
    return (
        "You are Maya reading a photo Zainal sent in Telegram. "
        f"Caption or request: {request}. "
        f"{language_instruction(request)} "
        "Answer the caption/request directly. If there is no caption, describe the useful visible details briefly. "
        "For people in the photo: do not identify who a person is from their face, do not verify that a person is Zainal "
        "or a named private person, and do not guess relationships from appearance. If asked who someone is, say you "
        "cannot identify people by face, then describe non-sensitive visible details such as clothing, pose, activity, "
        "scene, count of people, and any user-provided context from the caption. If Zainal gives a name or relationship "
        "in text, you may refer to that as user-provided context, not as face verification. "
        "Mention uncertainty if the image is blurry, cropped, too dark, or too small. "
        "If the photo contains a passport, ID, bank card, address, QR code, barcode, serial number, private key, token, "
        "or other sensitive private information, describe it generically and do not read or repeat the private value. "
        "Do not claim you can see live camera context; this is only the uploaded Telegram photo. "
        "Keep the reply concise and practical."
    )
