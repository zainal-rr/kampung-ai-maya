from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta

import aiosqlite

from canonical_memory import backfill_canonical_memory
from weekly_memory_store import save_weekly_summary
from time_parser import local_now

INTERNAL_PREF_MARKERS = (
    "chat_id", "work_location", "screen", "eye", "session", "status",
    "route", "cost", "usage", "active_workflow", "pending_browser_click",
    "voice_replies",
)
INTERNAL_TASK_ACTIONS = {"create_skill_scaffold", "send_message"}
TOPIC_STOPWORDS = {
    "about", "after", "again", "also", "because", "before", "being", "could",
    "doing", "explain", "from", "have", "hello", "maya", "minute", "more",
    "please", "right", "should", "tell", "that", "there", "this", "what",
    "when", "where", "which", "with", "would", "your",
}


@dataclass(frozen=True)
class WeeklyMemoryReport:
    run_key: str
    summary: str
    saved: bool


class WeeklyMemoryDistiller:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def run(self, *, save: bool = False, now: datetime | None = None) -> WeeklyMemoryReport:
        current = now or local_now()
        run_key = _week_key(current)
        cutoff = (current - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        await backfill_canonical_memory(self.db_path)
        data = await self._collect(cutoff)
        summary = self._summarize(run_key, data)
        if save:
            await save_weekly_summary(self.db_path, run_key=run_key, summary=summary, source="dry_run")
        return WeeklyMemoryReport(run_key, summary, save)

    async def _collect(self, cutoff: str) -> dict[str, list[dict[str, str]]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            return {
                "history": await _fetch_all(
                    db,
                    """
                    SELECT role, content, timestamp
                    FROM history
                    WHERE timestamp >= ?
                    ORDER BY timestamp DESC
                    LIMIT 40
                    """,
                    (cutoff,),
                ),
                "preferences": await _fetch_all(
                    db,
                    "SELECT key, value, source FROM preferences ORDER BY updated_at DESC LIMIT 8",
                ),
                "canonical": await _fetch_all(
                    db,
                    """
                    SELECT subject_key, content, confidence, source_channel
                    FROM canonical_memory_items
                    WHERE status = 'active'
                      AND temporary = 0
                      AND test_marker = 0
                      AND (expires_at IS NULL OR expires_at > datetime('now'))
                    ORDER BY pinned DESC, updated_at DESC
                    LIMIT 12
                    """,
                ),
                "lessons": await _fetch_all(
                    db,
                    """
                    SELECT normalized_rule, lesson_type, scope
                    FROM lessons
                    WHERE status = 'active'
                    ORDER BY created_at DESC, id DESC
                    LIMIT 8
                    """,
                ),
                "tasks": await _fetch_all(
                    db,
                    "SELECT title, status, due_at, action_type FROM tasks ORDER BY updated_at DESC LIMIT 12",
                ),
                "knowledge": await _fetch_all(
                    db,
                    "SELECT category, content FROM knowledge_base ORDER BY id DESC LIMIT 6",
                ),
            }

    @staticmethod
    def _summarize(run_key: str, data: dict[str, list[dict[str, str]]]) -> str:
        history = data["history"]
        preferences = [item for item in data["preferences"] if not _internal_preference(item.get("key", ""))]
        tasks = [item for item in data["tasks"] if item.get("action_type") not in INTERNAL_TASK_ACTIONS]
        open_tasks = [item for item in tasks if item.get("status") not in {"completed", "cancelled"}]
        completed = [item for item in tasks if item.get("status") == "completed"]
        lines = [
            f"Weekly memory dry run for {run_key}.",
            f"Conversation turns reviewed: {len(history)}.",
            f"Preferences available: {len(preferences)}.",
            f"Canonical memories available: {len(data['canonical'])}.",
            f"Lessons available: {len(data['lessons'])}.",
            f"Open tasks: {len(open_tasks)}. Completed tasks sampled: {len(completed)}.",
            f"Knowledge chunks sampled: {len(data['knowledge'])}.",
        ]
        lines.extend(_section("Preference signals", [item["value"] for item in preferences[:3]]))
        lines.extend(_section("Canonical facts", [item["content"] for item in data["canonical"][:4]]))
        lines.extend(_section("Recent lessons", [item["normalized_rule"] for item in data["lessons"][:3]]))
        lines.extend(_section("Recent conversation topics", _topic_highlights(history)))
        lines.extend(_section("Open loops", [item["title"] for item in open_tasks[:3]]))
        lines.append("Provider plan: Gemini first pass, Claude stewardship review, GPT only for high-value shaping.")
        lines.append("Provider calls used: none. This is safe to run before live API keys.")
        return "\n".join(lines)


async def _fetch_all(
    db: aiosqlite.Connection,
    query: str,
    params: tuple[str, ...] = (),
) -> list[dict[str, str]]:
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


def _section(title: str, values: list[str]) -> list[str]:
    if not values:
        return [f"{title}: none."]
    joined = "; ".join(value[:110] for value in values if value)
    return [f"{title}: {joined}."]


def _internal_preference(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in INTERNAL_PREF_MARKERS)


def _topic_highlights(history: list[dict[str, str]], limit: int = 6) -> list[str]:
    user_turns = [item["content"] for item in history if item.get("role") == "user"]
    assistant_turns = [item["content"] for item in history if item.get("role") == "assistant"]
    scores: dict[str, int] = {}
    for phrase in _topic_phrases(user_turns):
        scores[phrase] = scores.get(phrase, 0) + 6
    for token in _topic_tokens(" ".join(user_turns)):
        scores[token] = scores.get(token, 0) + 3
    for token in _topic_tokens(" ".join(assistant_turns)):
        scores[token] = scores.get(token, 0) + 1
    highlights = []
    for token, _ in sorted(scores.items(), key=lambda item: (-item[1], item[0])):
        if any(token in existing or existing in token for existing in highlights):
            continue
        highlights.append(token)
        if len(highlights) >= limit:
            break
    return highlights


def _topic_phrases(turns: list[str]) -> set[str]:
    phrases = set()
    for turn in turns:
        tokens = list(_ordered_topic_tokens(turn))
        for left, right in zip(tokens, tokens[1:]):
            phrases.add(f"{left} {right}")
    return phrases


def _ordered_topic_tokens(text: str) -> list[str]:
    import re

    return [
        token
        for token in re.findall(r"\b[a-z][a-z0-9]{3,}\b", text.lower())
        if token not in TOPIC_STOPWORDS
    ]


def _topic_tokens(text: str) -> set[str]:
    return set(_ordered_topic_tokens(text))


def _week_key(current: datetime) -> str:
    iso = current.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


async def _main() -> int:
    args = _args()
    report = await WeeklyMemoryDistiller(args.db).run(save=args.save)
    print(report.summary)
    print(f"saved: {'yes' if report.saved else 'no'}")
    return 0


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run no-key weekly memory distillation.")
    parser.add_argument("--db", default="session_history.db", help="SQLite database path.")
    parser.add_argument("--save", action="store_true", help="Save the generated weekly summary.")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
