from __future__ import annotations

import re
from pathlib import Path

from telegram import Bot

from voice import VoiceNode, spoken_preview
from vision_markup import split_image_marker


MAX_TELEGRAM_TEXT = 3900
MAX_TELEGRAM_CAPTION = 1024
FILE_MARKER = re.compile(r"^\[file:(?P<path>/[^\]\n]+)\]\s*$", re.MULTILINE)


async def send_text(bot: Bot, chat_id: int, text: str) -> None:
    clean_text, image_path = split_image_marker(text)
    clean_text, file_paths = split_file_markers(clean_text)
    chunks = _chunk_text(clean_text)
    if not chunks:
        chunks = []
    for chunk in chunks:
        await bot.send_message(chat_id=chat_id, text=chunk)
    if image_path and image_path.exists():
        try:
            with image_path.open("rb") as image_file:
                await bot.send_photo(chat_id=chat_id, photo=image_file)
        finally:
            image_path.unlink(missing_ok=True)
    for path in file_paths:
        await send_document_file(bot, chat_id, path, caption=path.name)


async def send_document_file(bot: Bot, chat_id: int, path: Path, caption: str = "") -> None:
    if not path.exists() or not path.is_file():
        return
    with path.open("rb") as document_file:
        await bot.send_document(
            chat_id=chat_id,
            document=document_file,
            caption=caption[:MAX_TELEGRAM_CAPTION] or None,
        )


async def send_speech(
    bot: Bot,
    chat_id: int,
    voice: VoiceNode,
    text: str,
    *,
    caption: str = "",
) -> None:
    text, _ = split_image_marker(text)
    text, _ = split_file_markers(text)
    audio_path = await voice.render_audio_file(spoken_preview(text, max_len=220))
    try:
        with audio_path.open("rb") as audio_file:
            await bot.send_audio(
                chat_id=chat_id,
                audio=audio_file,
                caption=caption[:MAX_TELEGRAM_CAPTION] or None,
                title="Maya",
                performer="Maya",
            )
    finally:
        await voice.cleanup_file(audio_path)


def _chunk_text(text: str) -> list[str]:
    clean = text.strip()
    if not clean:
        return []
    chunks = []
    while len(clean) > MAX_TELEGRAM_TEXT:
        split_at = clean.rfind("\n", 0, MAX_TELEGRAM_TEXT)
        if split_at <= 0:
            split_at = clean.rfind(" ", 0, MAX_TELEGRAM_TEXT)
        if split_at <= 0:
            split_at = MAX_TELEGRAM_TEXT
        chunks.append(clean[:split_at].strip())
        clean = clean[split_at:].strip()
    if clean:
        chunks.append(clean)
    return chunks


def split_file_markers(text: str) -> tuple[str, list[Path]]:
    paths = [Path(match.group("path")).expanduser() for match in FILE_MARKER.finditer(text)]
    clean = FILE_MARKER.sub("", text).strip()
    return clean, paths
