from __future__ import annotations

import asyncio
import base64
import json
import os
import subprocess
import tempfile
import wave
from pathlib import Path
from urllib.parse import urlencode

try:
    import websockets
except ImportError:
    websockets = None


def realtime_url() -> str:
    query = urlencode({"model": os.getenv("XAI_VOICE_AGENT_MODEL", "grok-voice-latest")})
    return f"wss://api.x.ai/v1/realtime?{query}"


def session_update_payload() -> dict:
    return {
        "type": "session.update",
        "session": {
            "modalities": ["text", "audio"],
            "instructions": os.getenv("XAI_VOICE_AGENT_INSTRUCTIONS", _default_instructions()),
            "voice": os.getenv("XAI_VOICE_AGENT_VOICE", "ara"),
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "turn_detection": {"type": None},
        },
    }


def conversation_item_payload(text: str) -> dict:
    return {
        "type": "conversation.item.create",
        "item": {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": text}],
        },
    }


def input_audio_append_payload(audio: bytes) -> dict:
    return {
        "type": "input_audio_buffer.append",
        "audio": base64.b64encode(audio).decode("ascii"),
    }


def input_audio_commit_payload() -> dict:
    return {"type": "input_audio_buffer.commit"}


def response_create_payload() -> dict:
    return {"type": "response.create", "response": {"modalities": ["text", "audio"]}}


class XaiRealtimeVoiceAgentTransport:
    def __init__(self):
        self.api_key = os.getenv("XAI_API_KEY")
        self.websocket = None
        self.spoke_audio = False
        self.sample_rate = int(os.getenv("XAI_VOICE_AGENT_SAMPLE_RATE", "24000"))
        self.timeout = int(os.getenv("XAI_VOICE_AGENT_RESPONSE_TIMEOUT", "60"))

    @property
    def speaks_for_itself(self) -> bool:
        return self.spoke_audio

    async def open(self) -> None:
        if not self.api_key:
            raise RuntimeError("XAI_API_KEY is required for real Grok Voice Agent mode.")
        if websockets is None:
            raise RuntimeError("websockets is required for real Grok Voice Agent mode.")
        self.websocket = await websockets.connect(
            realtime_url(),
            additional_headers={"Authorization": f"Bearer {self.api_key}"},
        )
        await self.websocket.send(json.dumps(session_update_payload()))

    async def send_text(self, text: str) -> str:
        if not self.websocket:
            await self.open()
        self.spoke_audio = False
        await self.websocket.send(json.dumps(conversation_item_payload(text)))
        await self.websocket.send(json.dumps(response_create_payload()))
        transcript, audio = await self._receive_response()
        if audio:
            await self._play_pcm_audio(audio)
            self.spoke_audio = True
        return transcript or "I heard you, but I did not get a text transcript back."

    async def send_audio(self, audio: bytes) -> str:
        if not self.websocket:
            await self.open()
        self.spoke_audio = False
        await self.websocket.send(json.dumps(input_audio_append_payload(audio)))
        await self.websocket.send(json.dumps(input_audio_commit_payload()))
        await self.websocket.send(json.dumps(response_create_payload()))
        transcript, output_audio = await self._receive_response()
        if output_audio:
            await self._play_pcm_audio(output_audio)
            self.spoke_audio = True
        return transcript or "I heard you, but I did not get a text transcript back."

    async def close(self) -> None:
        if self.websocket:
            await self.websocket.close()
            self.websocket = None

    async def _receive_response(self) -> tuple[str, bytes]:
        text_parts: list[str] = []
        audio_parts: list[bytes] = []
        while True:
            raw = await asyncio.wait_for(self.websocket.recv(), timeout=self.timeout)
            event = json.loads(raw)
            event_type = event.get("type", "")
            if event_type == "error":
                raise RuntimeError(_event_error(event))
            if event_type in {"response.output_audio_transcript.delta", "response.text.delta"}:
                text_parts.append(event.get("delta", ""))
            elif event_type == "response.output_audio.delta":
                audio_parts.append(base64.b64decode(event.get("delta", "")))
            elif event_type == "response.done":
                break
        return "".join(text_parts).strip(), b"".join(audio_parts)

    async def _play_pcm_audio(self, audio: bytes) -> None:
        path = await asyncio.to_thread(self._write_wav, audio)
        process = await asyncio.create_subprocess_exec(
            "afplay",
            str(path),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        await _cleanup_after_playback(process, path)

    def _write_wav(self, audio: bytes) -> Path:
        fd, filename = tempfile.mkstemp(prefix="maya-grok-voice-", suffix=".wav")
        os.close(fd)
        path = Path(filename)
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(self.sample_rate)
            output.writeframes(audio)
        return path


async def _cleanup_after_playback(process, path: Path) -> None:
    await process.wait()
    path.unlink(missing_ok=True)


def _event_error(event: dict) -> str:
    error = event.get("error") or {}
    if isinstance(error, dict):
        return error.get("message") or str(error)
    return str(error or event)


def _default_instructions() -> str:
    return (
        "You are Maya, Zainal's warm, direct iMac voice partner. "
        "Zainal is in Malaysia. Use Malaysia time, Asia/Kuala_Lumpur, for time questions. "
        "Keep spoken replies short, natural, and useful. "
        "Use Ara voice. Do not mention providers."
    )
