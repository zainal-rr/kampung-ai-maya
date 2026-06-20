from __future__ import annotations

import asyncio
import os
import tempfile
import struct
from pathlib import Path

from maya_core.audio_devices import bin_path, resolve_audio_input
from maya_core.execution_broker import CommandSpec, open_command_process_async


class VoiceAgentAudioCapture:
    def __init__(
        self,
        audio_device: str | None = None,
        duration_seconds: int | None = None,
        sample_rate: int | None = None,
        silence_duration: float | None = None,
        silence_threshold_db: int | None = None,
        min_rms: int | None = None,
        stop_on_silence: bool | None = None,
    ):
        self.audio_device = resolve_audio_input(audio_device or _primary_audio_input())
        self.duration_seconds = duration_seconds or int(os.getenv("IMAC_LISTEN_SECONDS", "4"))
        self.sample_rate = sample_rate or int(os.getenv("XAI_VOICE_AGENT_SAMPLE_RATE", "24000"))
        self.silence_duration = silence_duration or float(os.getenv("IMAC_SILENCE_DURATION", "0.35"))
        self.silence_threshold_db = silence_threshold_db or int(os.getenv("IMAC_SILENCE_THRESHOLD_DB", "-35"))
        self.min_rms = min_rms or int(os.getenv("XAI_VOICE_AGENT_MIN_RMS", "650"))
        self.stop_on_silence = _env_bool("IMAC_STOP_ON_SILENCE", True) if stop_on_silence is None else stop_on_silence

    async def listen_audio(self) -> bytes:
        with tempfile.TemporaryDirectory(prefix="maya-voice-agent-audio-") as tmp_dir:
            audio_path = Path(tmp_dir) / "turn.pcm"
            await self._record_pcm(audio_path)
            audio = await asyncio.to_thread(audio_path.read_bytes)
        if len(audio) < 1200 or _pcm16_rms(audio) < self.min_rms:
            return b""
        return audio

    async def _record_pcm(self, audio_path: Path) -> None:
        command = [
            bin_path("ffmpeg"),
            "-y",
            "-f",
            "avfoundation",
            "-i",
            self.audio_device,
            "-t",
            str(self.duration_seconds),
            "-ac",
            "1",
            "-ar",
            str(self.sample_rate),
            "-f",
            "s16le",
            str(audio_path),
        ]
        if self.stop_on_silence:
            command[6:6] = ["-af", f"silencedetect=noise={self.silence_threshold_db}dB:d={self.silence_duration}"]
        process, _argv, _sandboxed = await open_command_process_async(
            CommandSpec(
                argv=tuple(command),
                cwd=audio_path.parent,
                profile="media_capture",
                read_roots=(audio_path.parent,),
                write_roots=(audio_path.parent,),
                timeout=self.duration_seconds + 5,
                stdin_policy="pipe",
                capture_output=True,
                sandbox=False,
            )
        )
        if self.stop_on_silence:
            await self._stop_after_silence(process)
            return
        _, stderr = await process.communicate()
        if process.returncode != 0:
            raise RuntimeError(stderr.decode("utf-8", errors="ignore").strip() or "voice agent audio recording failed")

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


def _primary_audio_input() -> str:
    raw = os.getenv("IMAC_AUDIO_INPUT_NAMES") or os.getenv("IMAC_AUDIO_INPUTS") or os.getenv("IMAC_AUDIO_INPUT", ":0")
    return next((item.strip() for item in raw.split(",") if item.strip()), ":0")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _pcm16_rms(audio: bytes) -> float:
    sample_count = len(audio) // 2
    if sample_count <= 0:
        return 0.0
    samples = struct.unpack(f"<{sample_count}h", audio[: sample_count * 2])
    total = sum(sample * sample for sample in samples)
    return (total / sample_count) ** 0.5
