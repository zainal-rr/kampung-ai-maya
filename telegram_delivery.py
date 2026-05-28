from __future__ import annotations

import re
import asyncio
import os
import subprocess
from contextlib import suppress
from pathlib import Path

from audio_devices import bin_path
from telegram import Bot

from voice import VoiceNode
from vision_markup import split_image_marker
from workspace_paths import legacy_workspace_root, maya_workspace_root, project_roots


MAX_TELEGRAM_TEXT = 3900
MAX_TELEGRAM_CAPTION = 1024
FILE_MARKER = re.compile(r"^\[file:(?P<path>/[^\]\n]+)\]\s*$", re.MULTILINE)
ALLOWED_FILE_ROOTS = (maya_workspace_root, legacy_workspace_root)
ALLOWED_DOWNLOAD_PREFIXES = ("maya-", "kampung-")


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
):
    text, _ = split_image_marker(text)
    text, _ = split_file_markers(text)
    audio_path = await voice.render_audio_file(_telegram_voice_text(text))
    voice_note_path = None
    sent_message = None
    try:
        if os.getenv("TELEGRAM_SEND_VOICE_NOTE", "1") == "1":
            voice_note_path = await _voice_note_path(audio_path)
        if voice_note_path:
            with voice_note_path.open("rb") as voice_file:
                sent_message = await bot.send_voice(
                    chat_id=chat_id,
                    voice=voice_file,
                    caption=caption[:MAX_TELEGRAM_CAPTION] or None,
                )
        else:
            with audio_path.open("rb") as audio_file:
                sent_message = await bot.send_audio(
                    chat_id=chat_id,
                    audio=audio_file,
                    caption=caption[:MAX_TELEGRAM_CAPTION] or None,
                    title="Maya",
                    performer="Maya",
                )
    finally:
        if voice_note_path:
            with suppress(OSError):
                voice_note_path.unlink()
        await voice.cleanup_file(audio_path)
    return sent_message


def _telegram_voice_text(text: str) -> str:
    cleaned = _spokenize_telegram_reply(text)
    try:
        max_chars = int(os.getenv("TELEGRAM_VOICE_MAX_CHARS", "900"))
    except ValueError:
        max_chars = 900
    max_chars = max(160, max_chars)
    if len(cleaned) <= max_chars:
        return cleaned
    boundary = max(
        cleaned.rfind(".", 0, max_chars),
        cleaned.rfind("?", 0, max_chars),
        cleaned.rfind("!", 0, max_chars),
    )
    if boundary < int(max_chars * 0.6):
        boundary = cleaned.rfind(" ", 0, max_chars)
    if boundary <= 0:
        boundary = max_chars
    return cleaned[:boundary].strip() + "..."


def _spokenize_telegram_reply(text: str) -> str:
    text = re.sub(r"(?m)^\s*(?:#{1,6}\s+|\*\s+|-\s+|(?:\d+|[a-zA-Z])[\).]\s+)", "", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"(?m)^\s*[-*_]{3,}\s*$", "", text)
    return " ".join(text.split())


async def _voice_note_path(audio_path: Path) -> Path | None:
    ffmpeg = bin_path("ffmpeg")
    output_path = audio_path.with_suffix(".ogg")
    process = await asyncio.create_subprocess_exec(
        ffmpeg,
        "-y",
        "-i",
        str(audio_path),
        "-ac",
        "1",
        "-ar",
        "48000",
        "-c:a",
        "libopus",
        "-b:a",
        "32k",
        str(output_path),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    await process.wait()
    return output_path if process.returncode == 0 and output_path.exists() else None


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
    paths = [
        path
        for match in FILE_MARKER.finditer(text)
        if (path := _allowed_file_marker(Path(match.group("path")).expanduser())) is not None
    ]
    clean = FILE_MARKER.sub("", text).strip()
    return clean, paths


def _allowed_file_marker(path: Path) -> Path | None:
    try:
        resolved = path.resolve()
    except OSError:
        return None
    if any(_within(resolved, root()) for root in ALLOWED_FILE_ROOTS):
        return resolved
    if _allowed_download_file(resolved) or _allowed_project_doc(resolved):
        return resolved
    return None


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root.expanduser().resolve())
        return True
    except ValueError:
        return False


def _allowed_download_file(path: Path) -> bool:
    downloads = Path.home() / "Downloads"
    return _within(path, downloads) and path.name.lower().startswith(ALLOWED_DOWNLOAD_PREFIXES)


def _allowed_project_doc(path: Path) -> bool:
    return path.parent.name == "docs" and any(_within(path, root) for root in project_roots())
