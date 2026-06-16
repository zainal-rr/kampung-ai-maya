from __future__ import annotations

import os
import re
import time

from storage import get_preference, upsert_preference
from screen_session import deactivate_screen_sight
from vision_session import deactivate_guided_sight


def wake_phrases() -> tuple[str, ...]:
    raw = os.getenv("MAYA_WAKE_PHRASES", "hey maya,good morning maya,hello maya,maya")
    phrases = [item.strip().lower() for item in raw.split(",") if item.strip()]
    return tuple(sorted(phrases, key=len, reverse=True))


def split_wake_phrase(text: str) -> tuple[bool, str]:
    cleaned = " ".join(text.strip().split())
    for phrase in wake_phrases():
        words = [re.escape(word) for word in phrase.split()]
        pattern = r"^\s*" + r"[\s,.;!?]+".join(words) + r"\b[\s,.:;!?]*"
        match = re.match(pattern, cleaned, flags=re.IGNORECASE)
        if not match:
            continue
        return True, cleaned[match.end():].strip(" ,.:;!?")
    return False, cleaned


class WakeWindow:
    def __init__(self, seconds: int | None = None):
        self.seconds = seconds if seconds is not None else int(os.getenv("MAYA_WAKE_WINDOW_SECONDS", "5"))
        self.active_until = 0.0

    @property
    def active(self) -> bool:
        return time.time() <= self.active_until

    def apply(self, text: str) -> tuple[bool, str]:
        woke, command = split_wake_phrase(text)
        if woke:
            self.active_until = time.time() + self.seconds
            return True, command
        if self.active:
            self.active_until = time.time() + self.seconds
            return True, text.strip()
        return False, text.strip()


async def handle_activation_command(db_path: str, text: str) -> str | None:
    lowered = " ".join(text.lower().strip().split())
    if lowered in {"open imac", "open the imac", "change work location to imac"}:
        await upsert_preference(db_path, "work_location", "imac", source="telegram")
        return "Okay. I set your work location to iMac."
    if lowered in {"close maya eye", "close maya eyes", "stop seeing", "turn off maya eye"}:
        return await deactivate_guided_sight(db_path)
    if lowered in {"close imac", "change work location to telegram"}:
        await upsert_preference(db_path, "work_location", "telegram", source="telegram")
        await deactivate_guided_sight(db_path)
        await deactivate_screen_sight(db_path)
        return "Okay. I set your work location to Telegram and stopped seeing."
    return None


async def current_work_location(db_path: str) -> str:
    return await get_preference(db_path, "work_location") or "telegram"


def mudra_is_near(wearing: bool, distance_m: float | None) -> bool:
    threshold = float(os.getenv("MUDRA_ACTIVATION_DISTANCE_METRES", "1.0"))
    return wearing and distance_m is not None and distance_m <= threshold
