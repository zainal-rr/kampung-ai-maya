from __future__ import annotations

from datetime import datetime, timedelta

import aiosqlite

from storage import get_history, list_preferences, list_tasks
from time_parser import local_now
from weekly_memory_store import latest_weekly_summary


class BriefingBuilder:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def build(self, kind: str, channel: str) -> str:
        if kind == "morning_briefing":
            return await self._morning(channel)
        if kind == "evening_recap":
            return await self._evening(channel)
        if kind == "weekly_reflection":
            return await self._weekly(channel)
        return "I had a scheduled routine, but I do not have a briefing template for it yet."

    async def _morning(self, channel: str) -> str:
        tasks = await list_tasks(self.db_path, limit=5)
        soon = [item for item in tasks if self._is_due_soon(item.get("due_at"))][:3]
        waiting = [item for item in tasks if item.get("status") == "awaiting_confirmation"]
        lines = []
        if soon:
            lines.append("Upcoming: " + ", ".join(str(item["title"]) for item in soon))
        if waiting:
            lines.append(f"{len(waiting)} item still needs your approval.")
        if not lines:
            lines.append("Nothing urgent is queued right now.")
        return self._compose(channel, "Good morning. Here is your briefing.", lines)

    async def _evening(self, channel: str) -> str:
        history = await get_history(self.db_path, user_id=1, limit=4)
        tasks = await list_tasks(self.db_path, limit=5)
        carry = [str(item["title"]) for item in tasks[:2]]
        lines = []
        if history:
            recent = " | ".join(item["content"][:60] for item in history if item["content"].strip())
            lines.append(f"Recent flow: {recent[:180]}")
        if carry:
            lines.append("Carry-over: " + ", ".join(carry))
        if not lines:
            lines.append("Today stayed pretty quiet.")
        return self._compose(channel, "Evening recap.", lines)

    async def _weekly(self, channel: str) -> str:
        prepared = await latest_weekly_summary(self.db_path)
        if prepared:
            return self._compose(channel, "Weekly reflection.", _clean_weekly_summary(str(prepared["summary"])))
        completed, failed = await self._task_totals()
        preferences = await list_preferences(self.db_path, limit=2)
        lines = [f"Tasks completed this week: {completed}. Failed: {failed}."]
        if preferences:
            notes = ", ".join(item["value"][:70] for item in preferences)
            lines.append(f"Recent preference signals: {notes}")
        open_tasks = await list_tasks(self.db_path, limit=3)
        if open_tasks:
            lines.append("Open loops: " + ", ".join(str(item["title"]) for item in open_tasks[:3]))
        return self._compose(channel, "Weekly reflection.", lines)

    async def _task_totals(self) -> tuple[int, int]:
        async with aiosqlite.connect(self.db_path) as db:
            complete = await db.execute(
                "SELECT COUNT(*) FROM tasks WHERE status = 'completed' AND updated_at >= datetime('now', '-7 days')",
            )
            failed = await db.execute(
                "SELECT COUNT(*) FROM tasks WHERE status = 'failed' AND updated_at >= datetime('now', '-7 days')",
            )
            complete_row = await complete.fetchone()
            failed_row = await failed.fetchone()
        return int(complete_row[0]), int(failed_row[0])

    @staticmethod
    def _is_due_soon(due_at: str | None) -> bool:
        if not due_at:
            return False
        due = datetime.fromisoformat(due_at).astimezone(local_now().tzinfo)
        delta = due - local_now()
        return timedelta(hours=-12) <= delta <= timedelta(hours=12)

    @staticmethod
    def _compose(channel: str, title: str, lines: list[str]) -> str:
        if channel == "imac":
            return " ".join([title] + lines[:2])
        return title + "\n" + "\n".join(f"- {line}" for line in lines[:4])


def _clean_weekly_summary(summary: str) -> list[str]:
    facts = _extract_after(summary, "Canonical facts:")
    topics = _extract_after(summary, "Recent conversation topics:")
    loops = _extract_after(summary, "Open loops:")
    saved = _extract_count(summary, "Live canonical memories saved:")
    rejected = _extract_count(summary, "Live canonical memories rejected:")
    confirmation = _extract_count(summary, "Claude confirmation needed:")
    lines: list[str] = []
    if facts:
        lines.append("What I kept: " + _clean_list(facts, limit=2, skip_continuations=True))
    if topics:
        lines.append("Main thread: " + _clean_list(topics, limit=4))
    if loops and loops.lower() != "none":
        lines.append("Open loops: " + _clean_list(loops, limit=2))
    if saved or rejected or confirmation:
        parts = []
        if saved:
            parts.append(f"{saved} saved")
        if rejected:
            parts.append(f"{rejected} rejected")
        if confirmation:
            parts.append(f"{confirmation} needs confirmation")
        lines.append("Memory update: " + ", ".join(parts) + ".")
    if not lines:
        lines.append("I prepared the weekly memory summary, but there was nothing important enough to surface.")
    return lines[:4]


def _extract_after(summary: str, label: str) -> str:
    for line in summary.splitlines():
        stripped = line.strip()
        if stripped.startswith(label):
            return stripped.split(":", 1)[1].strip().rstrip(".")
    return ""


def _extract_count(summary: str, label: str) -> int:
    raw = _extract_after(summary, label)
    if not raw:
        return 0
    first = raw.split(".", 1)[0].strip()
    try:
        return int(first)
    except ValueError:
        return 0


def _clean_list(value: str, limit: int, skip_continuations: bool = False) -> str:
    items = [item.strip() for item in value.split(";") if item.strip()]
    cleaned = []
    seen = set()
    for item in items:
        if _internal_weekly_item(item):
            continue
        if skip_continuations and item[:1].islower():
            continue
        cleaned_item = _truncate_clean(item)
        key = cleaned_item.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(cleaned_item)
        if len(cleaned) >= limit:
            break
    if not cleaned:
        return "nothing user-facing"
    return _join(cleaned)


def _internal_weekly_item(item: str) -> bool:
    lowered = item.lower()
    markers = (
        "/users/",
        "{",
        "canonical memory ids",
        "provider plan",
        "provider calls",
        "gemini first pass",
        "claude stewardship",
    )
    return any(marker in lowered for marker in markers)


def _truncate_clean(item: str, limit: int = 120) -> str:
    text = " ".join(item.split()).strip(" .")
    if "; " in text:
        text = text.split("; ", 1)[0].strip(" .")
    if ". " in text:
        text = text.split(". ", 1)[0].strip(" .")
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,") + "."


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return items[0] if items else ""
    if len(items) == 2:
        return items[0] + "; " + items[1]
    return "; ".join(items[:-1]) + "; " + items[-1]
