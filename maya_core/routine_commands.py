from __future__ import annotations

import re

from maya_core.routine_store import create_or_update_routine, deactivate_routine, list_routines
from maya_core.time_parser import format_local_time, parse_clock_text, weekday_name, weekday_number


ROUTINES = {
    "morning_briefing": {
        "name": "Morning briefing",
        "phrases": ("morning briefing", "morning brief", "daily briefing"),
        "default_time": "08:00",
        "weekday": None,
    },
    "evening_recap": {
        "name": "Evening recap",
        "phrases": ("evening recap", "evening summary", "night recap"),
        "default_time": "21:00",
        "weekday": None,
    },
    "weekly_reflection": {
        "name": "Weekly reflection",
        "phrases": ("weekly reflection", "weekly review"),
        "default_time": "20:00",
        "weekday": 6,
    },
}


class RoutineCommandRouter:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def handle(self, text: str, channel: str) -> str | None:
        return (
            await self._handle_listing(text)
            or await self._handle_disable(text, channel)
            or await self._handle_create(text, channel)
        )

    async def _handle_listing(self, text: str) -> str | None:
        if text.lower() not in {"show my routines", "list my routines", "what are my routines"}:
            return None
        routines = await list_routines(self.db_path, active_only=True, limit=12)
        if not routines:
            return "You don't have any active routines yet."
        lines = [self._describe(item) for item in routines]
        return "Active routines:\n" + "\n".join(f"- {line}" for line in lines)

    async def _handle_disable(self, text: str, channel: str) -> str | None:
        if not re.match(r"^(?:disable|turn off|pause|stop)\b", text, re.IGNORECASE):
            return None
        kind = self._kind_from_text(text)
        if not kind:
            return None
        disabled = await deactivate_routine(self.db_path, kind=kind, channel=channel)
        if not disabled:
            return f"I don't have an active {ROUTINES[kind]['name'].lower()} on {channel}."
        return f"Okay. I turned off the {ROUTINES[kind]['name'].lower()} on {channel}."

    async def _handle_create(self, text: str, channel: str) -> str | None:
        if not re.match(r"^(?:set(?: up)?|create|schedule|enable|add)\b", text, re.IGNORECASE):
            return None
        kind = self._kind_from_text(text)
        if not kind:
            return None
        config = ROUTINES[kind]
        local_time = parse_clock_text(self._clock_phrase(text), default=config["default_time"])
        weekday = self._weekday(text, default=config["weekday"])
        routine_id = await create_or_update_routine(
            self.db_path,
            name=config["name"],
            kind=kind,
            channel=channel,
            local_time=local_time,
            weekday=weekday,
        )
        return f"Done. I set routine #{routine_id}: {self._describe({'name': config['name'], 'channel': channel, 'local_time': local_time, 'weekday': weekday})}."

    @staticmethod
    def _clock_phrase(text: str) -> str | None:
        match = re.search(r"\bat\s+([0-9: ]+(?:am|pm)?)\b", text, re.IGNORECASE)
        return match.group(1).strip() if match else None

    @staticmethod
    def _weekday(text: str, default: int | None) -> int | None:
        for name in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"):
            if name in text.lower():
                return weekday_number(name)
        return default

    @staticmethod
    def _kind_from_text(text: str) -> str | None:
        lowered = text.lower()
        for kind, config in ROUTINES.items():
            if any(phrase in lowered for phrase in config["phrases"]):
                return kind
        return None

    @staticmethod
    def _describe(item: dict[str, str | int | None]) -> str:
        when = f"every {weekday_name(item['weekday'])} at {format_local_time(str(item['local_time']))}"
        if item["weekday"] is None:
            when = f"every day at {format_local_time(str(item['local_time']))}"
        return f"{item['name']} on {item['channel']} {when}"
