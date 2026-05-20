from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass

from utils import OSBridge


APP_ALIASES = {
    "safari": "Safari",
    "chrome": "Google Chrome",
    "codex": "Codex",
    "telegram": "Telegram",
    "mail": "Mail",
    "notes": "Notes",
    "finder": "Finder",
    "powerpoint": "Microsoft PowerPoint",
    "word": "Microsoft Word",
}


@dataclass(frozen=True)
class ScreenContext:
    frontmost: str = "unknown"
    running_apps: tuple[str, ...] = ()
    requested_app: str = ""
    resolved_app: str = ""
    focused_app: str = ""
    focus_error: str = ""

    def to_prompt(self) -> str:
        apps = ", ".join(self.running_apps[:20]) or "unknown"
        lines = [
            "MacOS app state:",
            f"frontmost app before capture: {self.frontmost}",
            f"running apps from OS: {apps}",
        ]
        if self.requested_app:
            lines.append(f"named app requested by user: {self.requested_app}")
        if self.resolved_app:
            lines.append(f"matched running app: {self.resolved_app}")
        if self.focused_app:
            lines.append(f"screen was captured after bringing this app forward: {self.focused_app}")
        if self.focus_error:
            lines.append(f"named app focus failed: {self.focus_error}")
        return " ".join(lines) + " "


class ScreenContextProvider:
    def __init__(self, bridge: OSBridge | None = None):
        self.bridge = bridge or OSBridge()

    async def prepare(self, request: str) -> ScreenContext:
        frontmost, running = await asyncio.gather(
            self._frontmost(),
            self._running_apps(),
        )
        requested = self._requested_app(request)
        resolved = self._match_app(requested, running, frontmost)
        if requested and self._should_focus(request) and resolved:
            error = await self._focus(resolved)
            new_frontmost = await self._frontmost()
            return ScreenContext(new_frontmost, tuple(running), requested, resolved, "" if error else resolved, error)
        return ScreenContext(frontmost, tuple(running), requested, resolved)

    async def _frontmost(self) -> str:
        try:
            return await asyncio.to_thread(self.bridge.get_frontmost_app)
        except Exception:
            return "unknown"

    async def _running_apps(self) -> list[str]:
        try:
            apps = await asyncio.to_thread(self.bridge.list_running_apps)
            return [app for app in apps if app not in {"osascript", "System Events"}]
        except Exception:
            return []

    async def _focus(self, app: str) -> str:
        try:
            await asyncio.to_thread(self.bridge.switch_app, app)
            await asyncio.sleep(0.5)
            return ""
        except Exception as exc:
            return str(exc)

    @staticmethod
    def _requested_app(request: str) -> str:
        lowered = request.lower()
        for marker, app in APP_ALIASES.items():
            if marker in lowered:
                return app
        return ""

    @classmethod
    def _match_app(cls, requested: str, running: list[str], frontmost: str) -> str:
        if not requested:
            return ""
        for app in running:
            if cls._same_app(requested, app):
                return app
        if cls._same_app(requested, frontmost):
            return frontmost
        return ""

    @staticmethod
    def _same_app(left: str, right: str) -> bool:
        left_norm = re.sub(r"[^a-z0-9]+", "", left.lower())
        right_norm = re.sub(r"[^a-z0-9]+", "", right.lower())
        return bool(left_norm and right_norm and (left_norm == right_norm or left_norm in right_norm or right_norm in left_norm))

    @staticmethod
    def _should_focus(request: str) -> bool:
        lowered = request.lower()
        focus_markers = (
            "what is in", "what's in", "what about", "can you see what",
            "look at", "show me", "inside", "content", "page", "tab",
        )
        return any(marker in lowered for marker in focus_markers)
