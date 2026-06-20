from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from maya_core.audio_devices import bin_path
from maya_core.cost_tracker import record_usage
from maya_core.execution_broker import CommandSpec, run_command_async
from maya_voice.xai_stt import xai_transcribe_file


async def transcribe_telegram_voice(update, context, db_path: str) -> str:
    message = update.message
    attachment = getattr(message, "voice", None) or getattr(message, "audio", None)
    if not attachment:
        return ""
    with tempfile.TemporaryDirectory(prefix="maya-telegram-voice-") as tmp:
        input_path = Path(tmp) / "telegram_audio"
        wav_path = Path(tmp) / "telegram_audio.wav"
        telegram_file = await context.bot.get_file(attachment.file_id)
        await telegram_file.download_to_drive(custom_path=str(input_path))
        await _convert_to_wav(input_path, wav_path)
        duration = float(getattr(attachment, "duration", 0) or 0)
        transcript, paid_stt = await _transcribe_wav(wav_path)
        if paid_stt:
            await record_usage(db_path, "xai_stt_seconds", duration, "telegram voice note")
        return transcript.strip()


async def _convert_to_wav(input_path: Path, wav_path: Path) -> None:
    ffmpeg = bin_path("ffmpeg")
    result = await run_command_async(CommandSpec(
        argv=(ffmpeg, "-y", "-i", str(input_path), "-ac", "1", "-ar", "16000", str(wav_path)),
        cwd=wav_path.parent,
        profile="media",
        timeout=60,
        write_roots=(wav_path.parent,),
    ))
    if result.returncode != 0:
        message = bytes(result.stderr).decode("utf-8", errors="ignore").strip()
        raise RuntimeError(message or "Telegram voice conversion failed")


async def _transcribe_wav(wav_path: Path) -> tuple[str, bool]:
    api_key = os.getenv("XAI_API_KEY")
    if api_key:
        language = os.getenv("XAI_STT_LANGUAGE", "").strip() or None
        text = await asyncio.to_thread(xai_transcribe_file, api_key, wav_path, language)
        return text, True
    return await _transcribe_with_whisper(wav_path), False


async def _transcribe_with_whisper(wav_path: Path) -> str:
    whisper = bin_path("whisper")
    result = await run_command_async(CommandSpec(
        argv=(
            whisper,
            str(wav_path),
            "--model",
            os.getenv("WHISPER_MODEL", "tiny"),
            "--language",
            os.getenv("WHISPER_LANGUAGE", "en"),
            "--fp16",
            "False",
            "--condition_on_previous_text",
            "False",
            "--temperature",
            "0",
            "--output_format",
            "txt",
            "--output_dir",
            str(wav_path.parent),
        ),
        cwd=wav_path.parent,
        profile="media",
        timeout=300,
        write_roots=(wav_path.parent,),
    ))
    if result.returncode != 0:
        message = bytes(result.stderr).decode("utf-8", errors="ignore").strip()
        raise RuntimeError(message or "whisper transcription failed")
    return wav_path.with_suffix(".txt").read_text(encoding="utf-8")
