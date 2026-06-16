from __future__ import annotations

import asyncio
import contextlib
import os
from pathlib import Path
import time

from maya_core.assistant import KampungAssistant
from maya_voice.voice_agent_audio import VoiceAgentAudioCapture
from maya_voice.voice_agent_session import build_voice_agent_session
from maya_voice.voice_context import build_imac_voice_context
from maya_voice.xai_realtime_stream import XaiRealtimeStreamingSession
from maya_voice.xai_voice_handoff import (
    complete_voice_handoff_request,
    pop_voice_handoff_request,
)


class _NoopHotkeyListener:
    def stop(self) -> None:
        return


class HotkeyVoiceChannel:
    def __init__(
        self,
        assistant: KampungAssistant,
        audio_capture: VoiceAgentAudioCapture | None = None,
        hotkey: str | None = None,
        stop_hotkey: str | None = None,
    ):
        self.assistant = assistant
        self.audio_capture = audio_capture or VoiceAgentAudioCapture(
            duration_seconds=int(os.getenv("IMAC_HOTKEY_LISTEN_SECONDS", "8")),
            stop_on_silence=False,
        )
        self.hotkey = hotkey or os.getenv("MAYA_VOICE_HOTKEY", "<alt>+<space>")
        self.stop_hotkey = stop_hotkey or os.getenv("MAYA_VOICE_STOP_HOTKEY", "<alt>+<esc>")
        self.voice_agent = build_voice_agent_session(assistant.db_path)
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.running = False
        self.session_active = False
        self.stop_requested = False
        self.last_hotkey_at = 0.0
        self.streaming_session = None
        self.session_task: asyncio.Task | None = None
        self.trigger_path = Path(os.getenv("MAYA_VOICE_TRIGGER_FILE", ".maya_voice_trigger"))
        self.stop_trigger_path = Path(os.getenv("MAYA_VOICE_STOP_TRIGGER_FILE", ".maya_voice_stop"))
        self.toggle_trigger_path = Path(os.getenv("MAYA_VOICE_TOGGLE_TRIGGER_FILE", ".maya_voice_toggle"))
        self._trigger_mtime = self._mtime(self.trigger_path)
        self._stop_trigger_mtime = self._mtime(self.stop_trigger_path)
        self._toggle_trigger_mtime = self._mtime(self.toggle_trigger_path)

    async def run(self) -> None:
        self.running = True
        listener = self._start_hotkey_listener()
        file_trigger_task = asyncio.create_task(self._watch_file_triggers())
        print(
            f"Maya hotkey voice channel is live: start {self.hotkey}, stop {self.stop_hotkey}",
            flush=True,
        )
        try:
            while self.running:
                action = await self.queue.get()
                if action == "stop":
                    await self.stop_voice_session()
                    continue
                if action == "toggle":
                    await self.toggle_voice_session()
                    continue
                if self.session_task and self.session_task.done():
                    self.session_task = None
                    self.session_active = False
                if self.session_active or (self.session_task and not self.session_task.done()) or self._hotkey_debounced():
                    print("maya-hotkey> voice session already active", flush=True)
                    continue
                self.session_active = True
                self.session_task = asyncio.create_task(self._run_voice_session())
        finally:
            listener.stop()
            file_trigger_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await file_trigger_task

    def _start_hotkey_listener(self):
        backend = os.getenv("MAYA_HOTKEY_BACKEND", "carbon").lower()
        if backend in {"file", "files", "none", "disabled", "off"}:
            print("maya-hotkey> hotkey backend: file triggers only", flush=True)
            return _NoopHotkeyListener()
        if backend == "carbon":
            try:
                from maya_core.mac_hotkey import CarbonHotKeyListener

                loop = asyncio.get_running_loop()

                def on_hotkey() -> None:
                    print("maya-hotkey> start hotkey pressed", flush=True)
                    loop.call_soon_threadsafe(self.queue.put_nowait, "hotkey")

                def on_stop_hotkey() -> None:
                    print("maya-hotkey> stop hotkey pressed", flush=True)
                    loop.call_soon_threadsafe(self.queue.put_nowait, "stop")

                listener = CarbonHotKeyListener({
                    self.hotkey: on_hotkey,
                    self.stop_hotkey: on_stop_hotkey,
                })
                listener.start()
                print("maya-hotkey> hotkey backend: carbon", flush=True)
                return listener
            except Exception as exc:
                print(f"maya-hotkey> carbon hotkey backend failed, falling back to pynput: {exc}", flush=True)
        try:
            from pynput import keyboard
        except ImportError as exc:
            raise RuntimeError("pynput is required for Maya hotkey voice.") from exc

        loop = asyncio.get_running_loop()

        def on_hotkey() -> None:
            print("maya-hotkey> start hotkey pressed", flush=True)
            loop.call_soon_threadsafe(self.queue.put_nowait, "hotkey")

        def on_stop_hotkey() -> None:
            print("maya-hotkey> stop hotkey pressed", flush=True)
            loop.call_soon_threadsafe(self.queue.put_nowait, "stop")

        listener = keyboard.GlobalHotKeys({
            self.hotkey: on_hotkey,
            self.stop_hotkey: on_stop_hotkey,
        })
        listener.start()
        print("maya-hotkey> hotkey backend: pynput", flush=True)
        return listener

    async def _watch_file_triggers(self) -> None:
        while self.running:
            trigger_mtime = self._mtime(self.trigger_path)
            if trigger_mtime and trigger_mtime != self._trigger_mtime:
                self._trigger_mtime = trigger_mtime
                await self.queue.put("hotkey")
            stop_mtime = self._mtime(self.stop_trigger_path)
            if stop_mtime and stop_mtime != self._stop_trigger_mtime:
                self._stop_trigger_mtime = stop_mtime
                await self.queue.put("stop")
            toggle_mtime = self._mtime(self.toggle_trigger_path)
            if toggle_mtime and toggle_mtime != self._toggle_trigger_mtime:
                self._toggle_trigger_mtime = toggle_mtime
                await self.queue.put("toggle")
            await asyncio.sleep(0.2)

    @staticmethod
    def _mtime(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except FileNotFoundError:
            return 0.0

    async def stop_voice_session(self) -> None:
        self.stop_requested = True
        print("maya-hotkey> hard stop requested", flush=True)
        if self.streaming_session:
            await self.streaming_session.stop()
        current_task = asyncio.current_task()
        if self.session_task and not self.session_task.done() and self.session_task is not current_task:
            finalize_timeout = float(os.getenv("MAYA_VOICE_STOP_FINALIZE_TIMEOUT_SECONDS", "5"))
            try:
                await asyncio.wait_for(asyncio.shield(self.session_task), timeout=finalize_timeout)
            except asyncio.TimeoutError:
                print("maya-hotkey> voice session finalize timed out; cancelling task", flush=True)
                self.session_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self.session_task
        self.session_task = None
        await self.voice_agent.close("manual hotkey stop")
        self.session_active = False
        print("maya-hotkey> voice session manually stopped", flush=True)

    async def toggle_voice_session(self) -> None:
        if self.session_active or (self.session_task and not self.session_task.done()):
            await self.stop_voice_session()
            return
        if self.session_task and self.session_task.done():
            self.session_task = None
            self.session_active = False
        if self._hotkey_debounced():
            print("maya-hotkey> voice session toggle ignored by debounce", flush=True)
            return
        self.session_active = True
        self.session_task = asyncio.create_task(self._run_voice_session())

    async def _run_voice_session(self) -> None:
        self.stop_requested = False
        print("maya-hotkey> voice session started", flush=True)
        try:
            if not self.voice_agent.enabled:
                await self.assistant.voice.speak("Voice mode is off.")
                return
            if os.getenv("MAYA_HOTKEY_VOICE_MODE", "streaming") == "diagnostic":
                if os.getenv("MAYA_ENABLE_DIAGNOSTIC_FFMPEG_CAPTURE", "0") != "1":
                    print("maya-hotkey> diagnostic ffmpeg capture disabled", flush=True)
                    return
                await self._run_diagnostic_capture()
                return
            context = await build_imac_voice_context(self.assistant)
            stop_event = asyncio.Event()
            self.streaming_session = XaiRealtimeStreamingSession(
                self.assistant.db_path,
                context,
                stop_event,
                assistant=self.assistant,
            )
            await self.streaming_session.run()
        except Exception as exc:
            print(f"maya-hotkey-error> {exc}", flush=True)
            await self.voice_agent.close("hotkey voice error")
        finally:
            self.streaming_session = None
            if self.stop_requested:
                await self.voice_agent.close("manual hotkey stop")
            else:
                await self.voice_agent.close_if_idle()
            self.session_active = False
            if not self.stop_requested:
                await self._run_pending_voice_handoff()
            if self.session_task is asyncio.current_task():
                self.session_task = None
            print("maya-hotkey> voice session closed", flush=True)

    async def _run_diagnostic_capture(self) -> None:
        print("maya-hotkey> diagnostic capture", flush=True)
        audio = await self.audio_capture.listen_audio()
        if audio and not self.stop_requested:
            await self.voice_agent.start()
            response = await self.voice_agent.handle_audio(audio)
            print(f"maya-hotkey-reply> {response}", flush=True)
        await asyncio.sleep(int(os.getenv("XAI_VOICE_AGENT_IDLE_SECONDS", "20")))
        await self.voice_agent.close("idle timeout")

    async def _run_pending_voice_handoff(self) -> None:
        request = await pop_voice_handoff_request(self.assistant.db_path)
        if not request:
            return
        print(f"maya-hotkey-handoff> {request}", flush=True)
        try:
            response = await self.assistant.handle_text(request, channel="imac", speak_reply=True)
        except Exception as exc:
            await complete_voice_handoff_request(
                self.assistant.db_path,
                request,
                result=f"failed: {exc}",
                status="failed",
            )
            raise
        await complete_voice_handoff_request(self.assistant.db_path, request, result=response)
        print(f"maya-hotkey-handoff-reply> {response}", flush=True)

    def _hotkey_debounced(self) -> bool:
        now = time.monotonic()
        gap = float(os.getenv("MAYA_VOICE_HOTKEY_DEBOUNCE_SECONDS", "1.5"))
        if now - self.last_hotkey_at < gap:
            return True
        self.last_hotkey_at = now
        return False
