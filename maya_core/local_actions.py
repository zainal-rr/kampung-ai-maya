from __future__ import annotations

import asyncio
import re

from maya_core.utils import OSBridge


APP_ALIASES = {
    "chrome": "Google Chrome",
    "google chrome": "Google Chrome",
    "browser": "Google Chrome",
    "chrome browser": "Google Chrome",
    "google browser": "Google Chrome",
    "safari": "Safari",
    "telegram": "Telegram",
    "whatsapp": "WhatsApp",
    "word": "Microsoft Word",
    "microsoft word": "Microsoft Word",
    "powerpoint": "Microsoft PowerPoint",
    "microsoft powerpoint": "Microsoft PowerPoint",
    "codex": "Codex",
    "cursor": "Cursor",
    "terminal": "Terminal",
    "finder": "Finder",
}


class LocalActionRouter:
    def __init__(self, bridge: OSBridge | None = None):
        self.bridge = bridge or OSBridge()
        self.last_app: str | None = None

    async def handle(self, text: str) -> str | None:
        lowered = text.lower().strip()
        return (
            await self._frontmost_app(lowered)
            or await self._running_apps(lowered)
            or await self._where_last_app(lowered)
            or await self._volume_set(lowered)
            or await self._volume_delta(lowered)
            or await self._mute(lowered)
            or await self._press_shortcut(lowered)
            or await self._type_text(text)
            or await self._switch_app(text, lowered)
        )

    async def _frontmost_app(self, lowered: str) -> str | None:
        if lowered not in {"what app is open", "what app is frontmost", "what's open now"}:
            return None
        try:
            app = await asyncio.to_thread(self.bridge.get_frontmost_app)
        except Exception as exc:
            return f"I couldn't read the frontmost app right now: {exc}"
        return f"You're currently on {app}."

    async def _running_apps(self, lowered: str) -> str | None:
        if lowered not in {"list open apps", "what apps are open", "show open apps"}:
            return None
        try:
            apps = await asyncio.to_thread(self.bridge.list_running_apps)
        except Exception as exc:
            return f"I couldn't list the open apps right now: {exc}"
        visible = ", ".join(apps[:8]) if apps else "nothing obvious"
        return f"Open apps: {visible}."

    async def _where_last_app(self, lowered: str) -> str | None:
        if lowered.strip(" ?.") not in {"where", "where is it", "where did it open"}:
            return None
        if not self.last_app:
            return "Tell me which app you mean and I will check."
        try:
            frontmost = await asyncio.to_thread(self.bridge.get_frontmost_app)
        except Exception as exc:
            return f"I couldn't check where it opened: {exc}"
        if frontmost == self.last_app:
            return f"{self.last_app} is open in front on your iMac."
        return f"{self.last_app} was opened, but {frontmost} is currently in front."

    async def _volume_set(self, lowered: str) -> str | None:
        match = re.match(r"^(?:set )?volume(?: to)? (\d{1,3})$", lowered)
        if not match:
            return None
        level = max(0, min(100, int(match.group(1))))
        try:
            await asyncio.to_thread(self.bridge.set_volume, level)
        except Exception as exc:
            return f"I couldn't change the volume right now: {exc}"
        return f"Okay. Volume is now {level}%."

    async def _volume_delta(self, lowered: str) -> str | None:
        if lowered not in {"volume up", "turn it up", "volume down", "turn it down"}:
            return None
        delta = 10 if "up" in lowered else -10
        try:
            level = await asyncio.to_thread(self.bridge.change_volume, delta)
        except Exception as exc:
            return f"I couldn't change the volume right now: {exc}"
        return f"Done. Volume is now {level}%."

    async def _mute(self, lowered: str) -> str | None:
        if lowered == "mute":
            try:
                await asyncio.to_thread(self.bridge.mute)
            except Exception as exc:
                return f"I couldn't mute the audio right now: {exc}"
            return "Okay. Audio is muted."
        if lowered in {"unmute", "turn sound back on"}:
            try:
                await asyncio.to_thread(self.bridge.unmute)
            except Exception as exc:
                return f"I couldn't unmute the audio right now: {exc}"
            return "Okay. Audio is back on."
        return None

    async def _switch_app(self, text: str, lowered: str) -> str | None:
        body = _clean_command_prefix(text)
        match = re.match(r"^(?:open|switch to|focus|bring up|show me)\s+(.+)$", body, re.IGNORECASE)
        if not match:
            return None
        name = _resolve_app_name(match.group(1).strip(), self.last_app)
        if name is None:
            return "Tell me which app to open."
        try:
            await asyncio.to_thread(self.bridge.switch_app, name)
        except Exception as exc:
            return f"I couldn't switch to {name}: {exc}"
        self.last_app = name
        return f"Okay. I switched to {name}."

    async def _press_shortcut(self, lowered: str) -> str | None:
        match = re.match(r"^(?:press|hit)\s+(.+)$", lowered)
        if not match:
            return None
        shortcut = match.group(1).strip()
        try:
            await asyncio.to_thread(self.bridge.press_shortcut, shortcut)
        except Exception as exc:
            return f"I couldn't press {shortcut}: {exc}"
        return f"Done. I pressed {shortcut}."

    async def _type_text(self, text: str) -> str | None:
        match = re.match(r"^type\s+(.+)$", text, re.IGNORECASE)
        if not match:
            return None
        content = match.group(1).strip()
        try:
            await asyncio.to_thread(self.bridge.type_text, content)
        except Exception as exc:
            return f"I couldn't type that: {exc}"
        return "Done. I typed it into the frontmost app."


def _resolve_app_name(name: str, fallback: str | None = None) -> str | None:
    cleaned = _clean_app_phrase(name)
    lowered = cleaned.lower()
    if lowered in {"it", "that", "this"}:
        return fallback
    return APP_ALIASES.get(lowered, cleaned)


def _clean_app_phrase(name: str) -> str:
    cleaned = " ".join(name.strip().split())
    cleaned = re.sub(r"\s+(?:please|pls)$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(?:in|on)\s+(?:my|the|this)?\s*i?mac$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(?:my|the)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+app$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _clean_command_prefix(text: str) -> str:
    cleaned = " ".join(text.strip().split())
    cleaned = re.sub(
        r"^(?:maya\s+|please\s+|pls\s+|can you\s+|could you\s+|would you\s+|help me\s+)+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned.strip(" ?.!")
