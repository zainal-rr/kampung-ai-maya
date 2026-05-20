from __future__ import annotations

import os
import re
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}
DAYPARTS = {"morning": time(9, 0), "afternoon": time(15, 0), "evening": time(20, 0)}


def _tz() -> ZoneInfo:
    return ZoneInfo(os.getenv("KAMPUNG_TIMEZONE", "Asia/Kuala_Lumpur"))


def _with_clock(base: datetime, clock: time | None) -> datetime:
    if clock is None:
        return base
    return base.replace(hour=clock.hour, minute=clock.minute, second=0, microsecond=0)


def _parse_clock(raw: str | None, default: time | None = None) -> time | None:
    if not raw:
        return default
    match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", raw.strip(), re.IGNORECASE)
    if not match:
        return default
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = (match.group(3) or "").lower()
    if meridiem == "pm" and hour != 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    return time(hour % 24, minute)


def local_now() -> datetime:
    return datetime.now(_tz())


def parse_clock_text(raw: str | None, default: str = "09:00") -> str:
    fallback = _parse_clock(default)
    clock = _parse_clock(raw, fallback)
    return clock.strftime("%H:%M") if clock else default


def format_local_time(raw: str) -> str:
    hour_text, minute_text = raw.split(":", 1)
    clock = time(int(hour_text), int(minute_text))
    return clock.strftime("%I:%M %p %Z").replace("  ", " ").strip()


def weekday_number(name: str) -> int:
    return WEEKDAYS[name.lower()]


def weekday_name(index: int | None) -> str:
    if index is None:
        return "day"
    for name, value in WEEKDAYS.items():
        if value == index:
            return name.capitalize()
    return "day"


def extract_due_from_text(text: str) -> tuple[str, str | None]:
    now = local_now()

    relative = re.search(r"\s+in\s+(\d+)\s+(minute|minutes|hour|hours|day|days)\s*$", text, re.IGNORECASE)
    if relative:
        amount = int(relative.group(1))
        unit = relative.group(2).lower()
        delta = timedelta(minutes=amount)
        if "hour" in unit:
            delta = timedelta(hours=amount)
        elif "day" in unit:
            delta = timedelta(days=amount)
        due = now + delta
        return text[: relative.start()].strip(" ,."), due.astimezone(timezone.utc).isoformat()

    tomorrow = re.search(
        r"\s+tomorrow(?:\s+(morning|afternoon|evening))?(?:\s+at\s+([0-9: ]+(?:am|pm)?))?\s*$",
        text,
        re.IGNORECASE,
    )
    if tomorrow:
        due = now + timedelta(days=1)
        clock = _parse_clock(tomorrow.group(2), DAYPARTS.get((tomorrow.group(1) or "").lower(), time(9, 0)))
        due = _with_clock(due, clock)
        return text[: tomorrow.start()].strip(" ,."), due.astimezone(timezone.utc).isoformat()

    tonight = re.search(r"\s+tonight(?:\s+at\s+([0-9: ]+(?:am|pm)?))?\s*$", text, re.IGNORECASE)
    if tonight:
        due = _with_clock(now, _parse_clock(tonight.group(1), DAYPARTS["evening"]))
        if due <= now:
            due = due + timedelta(days=1)
        return text[: tonight.start()].strip(" ,."), due.astimezone(timezone.utc).isoformat()

    next_day = re.search(
        r"\s+next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
        r"(?:\s+at\s+([0-9: ]+(?:am|pm)?))?\s*$",
        text,
        re.IGNORECASE,
    )
    if next_day:
        target = WEEKDAYS[next_day.group(1).lower()]
        days_ahead = (target - now.weekday()) % 7 or 7
        due = now + timedelta(days=days_ahead)
        due = _with_clock(due, _parse_clock(next_day.group(2), time(9, 0)))
        return text[: next_day.start()].strip(" ,."), due.astimezone(timezone.utc).isoformat()

    return text.strip(), None


def format_due_text(due_at: str | None) -> str:
    if not due_at:
        return "with no due time yet"
    due = datetime.fromisoformat(due_at).astimezone(_tz())
    return f"for {due.strftime('%B %d, %Y %I:%M %p %Z')}"
