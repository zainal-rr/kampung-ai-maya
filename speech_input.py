import asyncio
import os
import subprocess
import tempfile
from pathlib import Path
from typing import List

from xai_stt import xai_transcribe_file


class FallbackTranscriptSource:
    async def listen(self) -> str:
        return await asyncio.to_thread(input, "maya-imac> ")


def detect_avfoundation_audio_devices() -> List[str]:
    result = subprocess.run(
        ["ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
        capture_output=True,
        text=True,
        check=False,
    )
    output = (result.stdout or "") + (result.stderr or "")
    devices = []
    for line in output.splitlines():
        if "AVFoundation audio devices:" in line:
            continue
        if "[AVFoundation indev" in line and "] [" in line:
            marker = line.split("] [", 1)[1]
            device = marker.split("]", 1)[0].strip()
            devices.append(device)
    return devices


class MacOSMicTranscriber:
    """
    Records a short clip from AVFoundation and transcribes it with the installed
    whisper CLI. If recording or transcription fails, we fall back to typed input.
    """

    def __init__(
        self,
        audio_device: str = ":0",
        duration_seconds: int = 4,
        whisper_model: str = "tiny",
        language: str = "en",
        silence_duration: float = 0.35,
        silence_threshold_db: int = -35,
    ):
        self.audio_device = audio_device
        self.duration_seconds = duration_seconds
        self.whisper_model = whisper_model
        self.language = language
        self.silence_duration = silence_duration
        self.silence_threshold_db = silence_threshold_db
        self.fallback = FallbackTranscriptSource()

    async def listen(self) -> str:
        try:
            return (await self._capture_and_transcribe()).strip()
        except Exception as exc:
            print("[LocalVoiceChannel] Mic capture failed. Falling back to typed transcript.")
            return await self.fallback.listen()

    async def _capture_and_transcribe(self) -> str:
        with tempfile.TemporaryDirectory() as tmp_dir:
            audio_path = Path(tmp_dir) / "mic.wav"
            print(
                "[LocalVoiceChannel] Recording until you stop speaking "
                f"(max {self.duration_seconds}s) from {self.audio_device}..."
            )
            await self._record_clip(audio_path)
            print("[LocalVoiceChannel] Transcribing...")
            transcript_path = await self._run_whisper(audio_path)
            return transcript_path.read_text(encoding="utf-8").strip()

    async def _record_clip(self, audio_path: Path) -> None:
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
            "16000",
            str(audio_path),
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
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
            raise RuntimeError(message or "ffmpeg recording failed")

    async def _run_whisper(self, audio_path: Path) -> Path:
        process = await asyncio.create_subprocess_exec(
            "whisper",
            str(audio_path),
            "--model",
            self.whisper_model,
            "--language",
            self.language,
            "--fp16",
            "False",
            "--condition_on_previous_text",
            "False",
            "--temperature",
            "0",
            "--output_format",
            "txt",
            "--output_dir",
            str(audio_path.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            message = stderr.decode("utf-8", errors="ignore").strip()
            raise RuntimeError(message or "whisper transcription failed")
        return audio_path.with_suffix(".txt")


class XAISttTranscriber(MacOSMicTranscriber):
    def __init__(
        self,
        api_key: str,
        audio_device: str = ":0",
        duration_seconds: int = 4,
        language: str = "en",
        silence_duration: float = 0.35,
        silence_threshold_db: int = -35,
    ):
        super().__init__(
            audio_device=audio_device,
            duration_seconds=duration_seconds,
            whisper_model="tiny",
            language=language,
            silence_duration=silence_duration,
            silence_threshold_db=silence_threshold_db,
        )
        self.api_key = api_key
        self.stt_url = "https://api.x.ai/v1/stt"

    async def _capture_and_transcribe(self) -> str:
        with tempfile.TemporaryDirectory() as tmp_dir:
            audio_path = Path(tmp_dir) / "mic.wav"
            print(
                "[LocalVoiceChannel] Recording until you stop speaking "
                f"(max {self.duration_seconds}s) from {self.audio_device}..."
            )
            await self._record_clip(audio_path)
            print("[LocalVoiceChannel] Sending audio to xAI STT...")
            return await asyncio.to_thread(self._transcribe_file, audio_path)

    def _transcribe_file(self, audio_path: Path) -> str:
        return xai_transcribe_file(self.api_key, audio_path, self.language)


class AutoTranscriptSource:
    def __init__(self, mic_source: MacOSMicTranscriber | None = None):
        self.mic_source = mic_source or MacOSMicTranscriber()
        self.manual_source = FallbackTranscriptSource()
        self._can_use_mic = self._probe_mic()

    @staticmethod
    def _probe_mic() -> bool:
        devices = detect_avfoundation_audio_devices()
        return bool(devices)

    async def listen(self) -> str:
        if self._can_use_mic:
            return await self.mic_source.listen()
        print("[LocalVoiceChannel] No visible macOS audio input devices. Using typed transcript mode.")
        return await self.manual_source.listen()


def build_transcript_source_from_env():
    mode, mic_source = _mic_source_from_env()
    xai_api_key = os.getenv("XAI_API_KEY")
    if mode in {"xai", "auto"} and xai_api_key:
        return XAISttTranscriber(
            api_key=xai_api_key,
            audio_device=mic_source.audio_device,
            duration_seconds=mic_source.duration_seconds,
            language=mic_source.language,
            silence_duration=mic_source.silence_duration,
            silence_threshold_db=mic_source.silence_threshold_db,
        )
    return _source_for_mode(mode, mic_source)


def build_wake_transcript_source_from_env():
    mode, mic_source = _mic_source_from_env()
    return _source_for_mode(mode, mic_source)


def _mic_source_from_env() -> tuple[str, MacOSMicTranscriber]:
    mode = os.getenv("IMAC_INPUT_MODE", "auto").lower()
    audio_device = os.getenv("IMAC_AUDIO_INPUT", ":0")
    duration_seconds = int(os.getenv("IMAC_LISTEN_SECONDS", "4"))
    silence_duration = float(os.getenv("IMAC_SILENCE_DURATION", "0.35"))
    silence_threshold_db = int(os.getenv("IMAC_SILENCE_THRESHOLD_DB", "-35"))
    language = os.getenv("IMAC_STT_LANGUAGE", os.getenv("WHISPER_LANGUAGE", "en"))
    mic_source = MacOSMicTranscriber(
        audio_device=audio_device,
        duration_seconds=duration_seconds,
        whisper_model=os.getenv("WHISPER_MODEL", "turbo"),
        language=language,
        silence_duration=silence_duration,
        silence_threshold_db=silence_threshold_db,
    )
    return mode, mic_source


def _source_for_mode(mode: str, mic_source: MacOSMicTranscriber):
    if mode == "mic":
        return mic_source
    if mode == "manual":
        return FallbackTranscriptSource()
    return AutoTranscriptSource(mic_source=mic_source)
