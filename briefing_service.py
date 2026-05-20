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
            return self._compose(channel, "Weekly reflection.", [prepared["summary"][:420]])
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
        return title + "\n" + "\n".join(f"- {line}" for line in lines[:3])
