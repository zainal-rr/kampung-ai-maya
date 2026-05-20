from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path


class VoiceAgentAudioCapture:
    def __init__(
        self,
        audio_device: str | None = None,
        duration_seconds: int | None = None,
        sample_rate: int | None = None,
        silence_duration: float | None = None,
        silence_threshold_db: int | None = None,
    ):
        self.audio_device = audio_device or os.getenv("IMAC_AUDIO_INPUT", ":0")
        self.duration_seconds = duration_seconds or int(os.getenv("IMAC_LISTEN_SECONDS", "4"))
        self.sample_rate = sample_rate or int(os.getenv("XAI_VOICE_AGENT_SAMPLE_RATE", "24000"))
        self.silence_duration = silence_duration or float(os.getenv("IMAC_SILENCE_DURATION", "0.35"))
        self.silence_threshold_db = silence_threshold_db or int(os.getenv("IMAC_SILENCE_THRESHOLD_DB", "-35"))

    async def listen_audio(self) -> bytes:
        with tempfile.TemporaryDirectory(prefix="maya-voice-agent-audio-") as tmp_dir:
            audio_path = Path(tmp_dir) / "turn.pcm"
            await self._record_pcm(audio_path)
            audio = await asyncio.to_thread(audio_path.read_bytes)
        return audio if len(audio) >= 1200 else b""

    async def _record_pcm(self, audio_path: Path) -> None:
        silence_filter = (
            f"silencedetect=noise={self.silence_threshold_db}dB:"
            f"d={self.silence_duration}"
        )
        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-y",
            "-f",
            "avfoundation",
            "-i",
            self.audio_device,
            "-af",
            silence_filter,
            "-t",
            str(self.duration_seconds),
            "-ac",
            "1",
            "-ar",
            str(self.sample_rate),
            "-f",
            "s16le",
            str(audio_path),
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        await self._stop_after_silence(process)

    @staticmethod
    async def _stop_after_silence(process) -> None:
        speech_started = False
        stderr_lines = []
        while True:
            line = await process.stderr.readline()
            if not line:
                break
            decoded = line.decode("utf-8", errors="ignore").strip()
            if decoded:
                stderr_lines.append(decoded)
            if "silence_end" in decoded:
                speech_started = True
            elif speech_started and "silence_start" in decoded and process.stdin:
                process.stdin.write(b"q\n")
                await process.stdin.drain()
                speech_started = False
        await process.wait()
        if process.returncode != 0:
            message = "\n".join(stderr_lines[-15:]).strip()
            raise RuntimeError(message or "voice agent audio recording failed")
