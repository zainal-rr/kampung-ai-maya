import asyncio
import os
import subprocess
import tempfile
from pathlib import Path

from maya_core.audio_devices import bin_path, device_names, resolve_audio_input
from maya_core.local_wake_scorer import LocalWakeScorerTranscriptSource
from maya_voice.voice_device_policy import current_local_wake_allowed
from xai_stt import xai_transcribe_file


class FallbackTranscriptSource:
    async def listen(self) -> str:
        try:
            return await asyncio.to_thread(input, "maya-imac> ")
        except EOFError:
            return ""


class SilentTranscriptSource:
    async def listen(self) -> str:
        return ""

def detect_avfoundation_audio_devices() -> list[str]:
    return device_names()

class MacOSMicTranscriber:
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
            print(f"[LocalVoiceChannel] Mic capture failed: {exc}")
            print("[LocalVoiceChannel] Falling back to typed transcript.")
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
            if not transcript_path.exists():
                return ""
            return transcript_path.read_text(encoding="utf-8").strip()

    async def _record_clip(self, audio_path: Path) -> None:
        silence_filter = (
            f"silencedetect=noise={self.silence_threshold_db}dB:"
            f"d={self.silence_duration}"
        )
        process = await asyncio.create_subprocess_exec(
            bin_path("ffmpeg"),
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
            bin_path("whisper"),
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
        super().__init__(audio_device, duration_seconds, "tiny", language, silence_duration, silence_threshold_db)
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


class MultiTranscriptSource:
    def __init__(self, sources: list[MacOSMicTranscriber]):
        self.sources = sources
        self.manual_source = FallbackTranscriptSource()

    async def listen(self) -> str:
        results = await asyncio.gather(
            *(self._listen_one(source) for source in self.sources),
            return_exceptions=True,
        )
        for result in results:
            transcript = "" if isinstance(result, Exception) else str(result).strip()
            if transcript:
                return transcript
        return await self.manual_source.listen()

    async def _listen_one(self, source: MacOSMicTranscriber) -> str:
        try:
            return (await source._capture_and_transcribe()).strip()
        except Exception as exc:
            print(f"[LocalVoiceChannel] Mic {source.audio_device} failed: {exc}")
            return ""


def build_transcript_source_from_env():
    mode, mic_sources = _mic_sources_from_env()
    xai_api_key = os.getenv("XAI_API_KEY")
    if mode in {"xai", "auto"} and xai_api_key:
        return _source_for_mode(mode, [_xai_source_from(source) for source in mic_sources])
    return _source_for_mode(mode, mic_sources)


def build_wake_transcript_source_from_env():
    if os.getenv("ENABLE_LOCAL_WAKE_SCORER", "0") == "1":
        if current_local_wake_allowed():
            return LocalWakeScorerTranscriptSource()
        return SilentTranscriptSource()
    mode, mic_sources = _mic_sources_from_env()
    if os.getenv("ENABLE_XAI_WAKE_STT", "0") == "1" and os.getenv("XAI_API_KEY"):
        mic_sources = [_xai_source_from(source) for source in mic_sources]
    return _source_for_mode(mode, mic_sources)


def _xai_source_from(source: MacOSMicTranscriber) -> XAISttTranscriber:
    return XAISttTranscriber(
        api_key=os.environ["XAI_API_KEY"],
        audio_device=source.audio_device,
        duration_seconds=source.duration_seconds,
        language=source.language,
        silence_duration=source.silence_duration,
        silence_threshold_db=source.silence_threshold_db,
    )
def build_call_transcript_source_from_env():
    mode, mic_sources = _mic_sources_from_env()
    call_sources = _sources_from_raw(os.getenv("IMAC_CALL_AUDIO_INPUT_NAMES", ""))
    return _source_for_mode(mode, [*mic_sources, *call_sources])


def _mic_sources_from_env() -> tuple[str, list[MacOSMicTranscriber]]:
    mode = os.getenv("IMAC_INPUT_MODE", "auto").lower()
    raw_devices = (
        os.getenv("IMAC_AUDIO_INPUT_NAMES")
        or os.getenv("IMAC_AUDIO_INPUTS")
        or os.getenv("IMAC_AUDIO_INPUT", ":0")
    )
    return mode, _sources_from_raw(raw_devices)

def _sources_from_raw(raw_devices: str) -> list[MacOSMicTranscriber]:
    audio_devices = [device.strip() for device in raw_devices.split(",") if device.strip()]
    duration_seconds = int(os.getenv("IMAC_LISTEN_SECONDS", "4"))
    silence_duration = float(os.getenv("IMAC_SILENCE_DURATION", "0.35"))
    silence_threshold_db = int(os.getenv("IMAC_SILENCE_THRESHOLD_DB", "-35"))
    language = os.getenv("IMAC_STT_LANGUAGE", os.getenv("WHISPER_LANGUAGE", "en"))
    return [
        MacOSMicTranscriber(
            audio_device=resolve_audio_input(device),
            duration_seconds=duration_seconds,
            whisper_model=os.getenv("WHISPER_MODEL", "turbo"),
            language=language,
            silence_duration=silence_duration,
            silence_threshold_db=silence_threshold_db,
        )
        for device in audio_devices
    ]

def _source_for_mode(mode: str, mic_sources: list[MacOSMicTranscriber]):
    if mode == "mic":
        return MultiTranscriptSource(mic_sources)
    if mode == "manual":
        return FallbackTranscriptSource()
    return AutoTranscriptSource(mic_source=MultiTranscriptSource(mic_sources))
