from __future__ import annotations

import os
import re
import logging

from cost_tracker import record_usage
from language_policy import language_instruction
from models import TheSenses
from screen_context import ScreenContext, ScreenContextProvider
from screen_service import MacScreenService, ScreenSnapshot
from screen_session import screen_sight_active
from storage import upsert_preference


SCREEN_MARKERS = (
    "look at my screen",
    "look at the screen",
    "my screen",
    "screen",
    "powerpoint",
    "slide",
    "diagram",
    "photo",
    "image",
    "what should i click",
    "what is open",
    "what app",
    "what apps",
    "open apps",
    "apps open",
    "app is open",
    "apps is open",
    "window",
    "browser",
    "tab",
    "safari",
    "codex",
    "this slide",
    "this page",
    "this document",
    "put this",
    "move this",
    "what about now",
    "does this",
    "should i",
)


class ScreenResponder:
    def __init__(self, db_path: str, capture_service=None, senses=None, context_provider=None):
        self.db_path = db_path
        self.capture_service = capture_service or MacScreenService()
        self.context_provider = context_provider or ScreenContextProvider()
        self.senses = senses or TheSenses(
            os.getenv("GOOGLE_API_KEY", "dummy"),
            os.getenv("GEMINI_FLASH_MODEL", "gemini-3.1-flash"),
        )
        self.premium_senses = senses or TheSenses(
            os.getenv("GOOGLE_API_KEY", "dummy"),
            os.getenv("GEMINI_PREMIUM_MODEL", "gemini-3.5-flash"),
        )

    async def handle(self, text: str, channel: str) -> str | None:
        explicit = self._explicit_command(text)
        active = await screen_sight_active(self.db_path)
        if not self._is_query(text, channel, active, explicit):
            return None
        context = await self.context_provider.prepare(text)
        state_reply = self._app_state_reply(text, context)
        if state_reply:
            await upsert_preference(self.db_path, "maya_screen_last_status", "visible: macOS app state checked", source="screen")
            return state_reply
        snapshot = self.capture_service.capture_once()
        await self._record_snapshot(snapshot)
        if not snapshot.visible or not snapshot.image_bytes:
            return f"I can't see your screen right now. {snapshot.status}"
        return await self._describe(text, snapshot, context)

    @classmethod
    def _app_state_reply(cls, request: str, context: ScreenContext) -> str:
        lowered = request.lower()
        if context.requested_app and not context.resolved_app:
            return f"{context.requested_app} is not open in your iMac app list right now."
        if context.requested_app and context.resolved_app and cls._is_named_app_open_question(lowered):
            frontmost = context.frontmost or "unknown"
            if cls._same_app(context.resolved_app, frontmost):
                return f"Yes, {context.resolved_app} is open and it is currently frontmost."
            return f"Yes, {context.resolved_app} is open. Frontmost app: {frontmost}."
        if cls._is_open_apps_question(lowered):
            apps = ", ".join(context.running_apps[:12]) or "nothing obvious"
            return f"Open apps from macOS: {apps}. Frontmost app: {context.frontmost}."
        return ""

    @staticmethod
    def _is_open_apps_question(lowered: str) -> bool:
        markers = (
            "what apps", "which apps", "open apps", "apps open",
            "app is open", "apps is open", "application is open",
            "applications are open",
        )
        return any(marker in lowered for marker in markers)

    @staticmethod
    def _is_named_app_open_question(lowered: str) -> bool:
        content_markers = (
            "what is in", "what's in", "content", "inside", "page", "tab",
            "what does", "what did", "read", "say",
        )
        if any(marker in lowered for marker in content_markers):
            return False
        return any(marker in lowered for marker in (" open", "opened", "running", "do i have", "can you see"))

    @staticmethod
    def _explicit_command(text: str) -> bool:
        return text.lower().strip().startswith("look at my screen")

    @classmethod
    def _is_query(cls, text: str, channel: str, active: bool, explicit: bool) -> bool:
        lowered = " ".join(text.lower().split())
        if channel == "imac":
            return cls._looks_like_screen_question(lowered)
        if explicit:
            return True
        if not active:
            return False
        return cls._looks_like_screen_question(lowered) or cls._mentions_known_app(lowered) or cls._screen_followup(lowered)

    @staticmethod
    def _looks_like_screen_question(lowered: str) -> bool:
        if any(marker in lowered for marker in SCREEN_MARKERS):
            return True
        if lowered.startswith(("can you see", "can you read", "what is in", "what's in")):
            return True
        app_words = ("safari", "chrome", "codex", "telegram", "mail", "notes", "finder", "powerpoint")
        context_words = ("see", "open", "opened", "in ", "inside", "showing", "visible", "window", "tab")
        return any(app in lowered for app in app_words) and any(word in lowered for word in context_words)

    @staticmethod
    def _mentions_known_app(lowered: str) -> bool:
        app_words = ("safari", "chrome", "codex", "telegram", "mail", "notes", "finder", "powerpoint", "word")
        return any(app in lowered for app in app_words)

    @staticmethod
    def _screen_followup(lowered: str) -> bool:
        starters = (
            "what about now", "how about now", "does this", "is this",
            "should i", "can you read", "can you see", "what should i",
        )
        referents = ("this", "here", "there", "layout", "slide", "page", "document", "diagram")
        return lowered.startswith(starters) or any(word in lowered for word in referents)

    @staticmethod
    def _same_app(left: str, right: str) -> bool:
        left_norm = re.sub(r"[^a-z0-9]+", "", left.lower())
        right_norm = re.sub(r"[^a-z0-9]+", "", right.lower())
        return bool(left_norm and right_norm and (left_norm == right_norm or left_norm in right_norm or right_norm in left_norm))

    async def _describe(self, request: str, snapshot: ScreenSnapshot, context: ScreenContext) -> str:
        prompt = (
            "You are Maya looking at Zainal's current iMac screen. "
            f"User request: {request}. "
            f"{context.to_prompt()}"
            "Help with what is visible on the screen, such as slides, photos, diagrams, documents, "
            "browser pages, or app windows. Use this fresh view for the current question. "
            "If text is too small or hidden, ask Zainal to zoom in or bring the window forward. "
            "If the user asks what to click, describe the visible target in words. "
            "For open-app questions, use the macOS app state as source of truth for which apps are open, "
            "and use the screenshot only for what is visibly on screen. "
            "A running app is not the same as visible contents. "
            "If a named app was brought forward before capture, describe what is now visible in that app. "
            "If a named app is running but not visible and was not brought forward, say it is open but not visible. "
            "Since you are receiving a screenshot, never say you can only see chat text. "
            "Keep the answer natural and concise. "
            f"{language_instruction(request)} "
            "Do not mention model providers. End with CONFIDENCE: 0-100."
        )
        try:
            answer = (await self.senses.describe_image(snapshot.image_bytes, prompt)).strip()
            await record_usage(self.db_path, "gemini_flash_vision_calls", 1, "screen snapshot")
        except Exception as exc:
            logging.warning("Screen vision model failed: %s", exc)
            return self._fallback_description(context)
        if self._should_escalate(request, answer):
            try:
                premium_answer = await self.premium_senses.describe_image(snapshot.image_bytes, prompt)
                await record_usage(self.db_path, "gemini_premium_vision_calls", 1, "screen escalation")
                answer = premium_answer.strip() or answer
            except Exception as exc:
                logging.warning("Screen vision escalation failed: %s", exc)
        clean = self._remove_confidence(answer)
        return f"I see it. {clean}" if clean else "I can see it, but I can't read it clearly yet."

    @staticmethod
    def _fallback_description(context: ScreenContext) -> str:
        if context.resolved_app:
            return (
                f"I can confirm {context.resolved_app} is open, but I can't read the screen content "
                "right now because the vision model is unavailable."
            )
        return "I captured your screen, but I can't read the content right now because the vision model is unavailable."

    async def _record_snapshot(self, snapshot: ScreenSnapshot) -> None:
        visible = "visible" if snapshot.visible else "not visible"
        await upsert_preference(self.db_path, "maya_screen_last_status", f"{visible}: {snapshot.status}", source="screen")

    @classmethod
    def _should_escalate(cls, request: str, answer: str) -> bool:
        lowered_request = request.lower()
        lowered_answer = answer.lower()
        if "look carefully" in lowered_request or "double check" in lowered_request:
            return True
        if any(marker in lowered_request for marker in ("tiny text", "small text", "architecture", "complex diagram")):
            return True
        confidence = cls._confidence(answer)
        uncertain = any(marker in lowered_answer for marker in ("unclear", "too small", "can't read", "cannot read"))
        return uncertain or (confidence is not None and confidence < 60)

    @staticmethod
    def _confidence(answer: str) -> int | None:
        match = re.search(r"CONFIDENCE:\s*(\d{1,3})", answer, re.IGNORECASE)
        if not match:
            return None
        return max(0, min(100, int(match.group(1))))

    @staticmethod
    def _remove_confidence(text: str) -> str:
        return re.sub(r"\s*CONFIDENCE:\s*\d{1,3}", "", text, flags=re.IGNORECASE).strip()
