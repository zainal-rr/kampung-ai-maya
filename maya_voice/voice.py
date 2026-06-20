import os
import asyncio
import uuid
from pathlib import Path
from shutil import which
try:
    import aiohttp
except ImportError:
    aiohttp = None

from maya_core.cost_tracker import record_usage
from maya_core.execution_broker import CommandSpec, run_command_async
from maya_core.repo_paths import repo_root


def spoken_preview(text: str, max_len: int = 160) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_len:
        return cleaned
    for marker in (".", "!", "?"):
        index = cleaned.find(marker)
        if 0 < index <= max_len:
            return cleaned[: index + 1].strip()
    return cleaned[: max_len - 3].rstrip() + "..."


class VoiceNode:
    """
    The 'Larynx' of Kampung AI.
    Handles Text-to-Speech generation via xAI Grok TTS and playback via macOS afplay.
    """
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or os.getenv("KAMPUNG_DB_PATH")
        self.api_key = os.getenv("XAI_API_KEY")
        self.tts_url = "https://api.x.ai/v1/tts"
        self.log_dir = repo_root(__file__) / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.local_voice_en = os.getenv("MACOS_SAY_VOICE_EN", "Flo (English (US))")
        self.local_voice_ms = os.getenv("MACOS_SAY_VOICE_MS", "Amira")
        self.default_voice = "ara"
        self.malay_keywords = ["apa", "saya", "kamu", "terima", "kasih", "makan", "minum", "khabar"]

    def _detect_language(self, text: str) -> str:
        """
        Simple detection for Mirror Mode. 
        Returns 'id' for Malay/Indonesian-adjacent phrasing or 'en' for English.
        """
        text_lower = text.lower()
        if any(word in text_lower for word in self.malay_keywords):
            return "id"
        return "en"

    async def speak(self, text: str, voice: str = None):
        if not text:
            return
        audio_path = await self.render_audio_file(text, voice=voice)
        asyncio.create_task(self._play_and_cleanup(audio_path))

    async def render_audio_file(self, text: str, voice: str = None) -> Path:
        if not text:
            raise ValueError("Cannot render empty speech.")

        selected_voice = voice or self.default_voice
        lang = self._detect_language(text)

        print(f"[VoiceNode] Detected language: {lang}. Using voice: {selected_voice}")

        if not self.api_key:
            return await self._render_with_macos(text, lang)
        if aiohttp is None:
            raise RuntimeError("aiohttp is required for xAI TTS. Install dependencies or use local voice fallback.")
        audio_path = await self._render_with_xai(text, selected_voice, lang)
        await record_usage(self.db_path, "ara_tts_chars", len(text), "tts")
        return audio_path

    async def _render_with_xai(self, text: str, selected_voice: str, lang: str) -> Path:
        temp_filename = self.log_dir / f"speech_{uuid.uuid4().hex}.mp3"
        try:
            payload = {
                "text": text,
                "voice_id": selected_voice,
                "language": lang,
                "output_format": {
                    "codec": "mp3",
                    "sample_rate": 24000,
                    "bit_rate": 128000
                }
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.tts_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                ) as response:
                    if response.status >= 400:
                        error_text = await response.text()
                        raise RuntimeError(f"xAI TTS error {response.status}: {error_text}")

                    audio_bytes = await response.read()

            await asyncio.to_thread(temp_filename.write_bytes, audio_bytes)
            return temp_filename
        except Exception as e:
            print(f"[VoiceNode] Error: {e}")
            if temp_filename.exists():
                temp_filename.unlink()
            raise

    async def _render_with_macos(self, text: str, lang: str) -> Path:
        selected_voice = self.local_voice_ms if lang == "id" else self.local_voice_en
        raw_path = self.log_dir / f"speech_{uuid.uuid4().hex}.aiff"
        final_path = self.log_dir / f"speech_{uuid.uuid4().hex}.m4a"
        result = await run_command_async(CommandSpec(
            argv=("say", "-v", selected_voice, "-o", str(raw_path), text),
            cwd=raw_path.parent,
            profile="gui",
            timeout=60,
            write_roots=(raw_path.parent,),
            capture_output=False,
            sandbox=False,
        ))
        if result.returncode != 0:
            raise RuntimeError("macOS say synthesis failed")
        if which("ffmpeg"):
            convert = await run_command_async(CommandSpec(
                argv=("ffmpeg", "-y", "-i", str(raw_path), str(final_path)),
                cwd=raw_path.parent,
                profile="media",
                timeout=60,
                write_roots=(raw_path.parent,),
                capture_output=False,
            ))
            if convert.returncode == 0:
                await self.cleanup_file(raw_path)
                return final_path
        return raw_path

    async def cleanup_file(self, file_path: Path) -> None:
        await asyncio.to_thread(self._remove_file, file_path)

    async def _play_and_cleanup(self, file_path: Path):
        await run_command_async(CommandSpec(
            argv=("afplay", str(file_path)),
            cwd=file_path.parent,
            profile="gui",
            timeout=300,
            capture_output=False,
            sandbox=False,
        ))
        await self.cleanup_file(file_path)

    @staticmethod
    def _remove_file(file_path: Path) -> None:
        try:
            if file_path.exists():
                file_path.unlink()
        except Exception as e:
            print(f"[VoiceNode] Cleanup Error: {e}")

# Example Usage (Commented out for integration)
# if __name__ == "__main__":
#     async def main():
#         v = VoiceNode()
#         await v.speak("Apa khabar, Zainal? Saya sudah bersedia.")
#         await asyncio.sleep(5) # Give it time to play
#     asyncio.run(main())
