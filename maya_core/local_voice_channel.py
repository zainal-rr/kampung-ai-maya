import asyncio
import os

from maya_core.activation import WakeWindow
from maya_core.assistant import KampungAssistant
from maya_core.imac_voice_policy import decide_imac_voice_route
from speech_input import (
    build_transcript_source_from_env,
    build_wake_transcript_source_from_env,
)
from voice_agent_session import build_voice_agent_session


class LocalVoiceChannel:
    def __init__(self, assistant: KampungAssistant, transcript_source=None, wake_source=None, audio_capture=None):
        self.assistant = assistant
        self.transcript_source = transcript_source or build_transcript_source_from_env()
        self.wake_source = wake_source or transcript_source or build_wake_transcript_source_from_env()
        self.wake_window = WakeWindow()
        self.voice_agent = build_voice_agent_session(assistant.db_path)
        self.audio_capture = audio_capture
        self.running = False

    async def run(self):
        self.running = True
        print("Local iMac channel is live. Speak after the prompt. Say or type 'exit' to stop.")

        while self.running:
            print("maya-imac> listening...")
            if self.wake_window.active and self.voice_agent.enabled:
                await self._handle_policy_turn(self.transcript_source)
                continue
            source = await self._current_source()
            transcript = (await source.listen()).strip()
            if not transcript:
                print("maya-imac> no speech captured")
                await self.voice_agent.close_if_idle()
                continue
            if os.getenv("MAYA_WAKE_DEBUG", "0") == "1":
                print(f"maya-imac-wake-debug> {transcript[:80]}")
            if transcript.lower() in {"exit", "quit"}:
                await self.voice_agent.close("local channel stopped")
                self.running = False
                break
            active, command = self.wake_window.apply(transcript)
            if not active:
                await self.voice_agent.close_if_idle()
                print("maya-imac> waiting for wake phrase")
                continue
            if not command:
                await self.voice_agent.start()
                if not self.voice_agent.enabled:
                    await self.assistant.voice.speak("I'm here.")
                continue
            if self.voice_agent.enabled:
                await self._handle_policy_text(command)
                continue
            transcript = command
            print(f"maya-imac-heard> {transcript}")

            response = await self.assistant.handle_text(
                transcript,
                channel="imac",
                speak_reply=True,
            )
            print(f"maya-imac-reply> {response}")

    async def _handle_policy_turn(self, source) -> None:
        transcript = (await source.listen()).strip()
        if not transcript:
            await self.voice_agent.close_if_idle()
            print("maya-imac-agent> waiting inside wake window")
            return
        await self._handle_policy_text(transcript)

    async def _handle_policy_text(self, transcript: str) -> None:
        decision = decide_imac_voice_route(transcript)
        print(f"maya-imac-policy> {decision.route}: {decision.reason}")
        if decision.route == "grok":
            response = await self.voice_agent.handle_text(transcript)
        else:
            await self.voice_agent.close("handoff to Maya text lane")
            if decision.filler and self.assistant.voice.api_key:
                await self.assistant.voice.speak(decision.filler)
            routed = "[sight]" + transcript if decision.route == "gemini" else transcript
            response = await self.assistant.handle_text(routed, channel="imac", speak_reply=True)
        print(f"maya-imac-agent> {response}")

    async def _current_source(self):
        if self.wake_window.active:
            return self.transcript_source
        return self.wake_source
