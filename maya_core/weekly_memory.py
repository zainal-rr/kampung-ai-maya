from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta

import aiosqlite

from weekly_memory_helpers import (
    INTERNAL_TASK_ACTIONS,
    _canonical_memory_ids,
    _fetch_all,
    _internal_preference,
    _section,
    _topic_highlights,
    _week_key,
)
from maya_memory.canonical_memory_backfill import backfill_canonical_memory
from maya_core.lesson_store import init_lesson_db
from maya_core.retention_policy import run_retention_cleanup
from storage import init_db
from time_parser import local_now
from weekly_memory_live import ProviderCall, live_weekly_canonical_distillation
from weekly_memory_providers import weekly_distiller_agent, weekly_reviewer_agent
from weekly_memory_store import finish_weekly_memory_run, save_weekly_summary, start_weekly_memory_run
from weekly_memory_store import init_weekly_memory_db


@dataclass(frozen=True)
class WeeklyMemoryReport:
    run_key: str
    summary: str
    saved: bool
    run_audit_id: int = 0
    canonical_saved: int = 0
    canonical_rejected: int = 0
    provider_calls: int = 0
    canonical_memory_ids: tuple[str, ...] = ()
    confirmation_needed: tuple[str, ...] = ()


class WeeklyMemoryDistiller:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def run(
        self,
        *,
        save: bool = False,
        now: datetime | None = None,
        live: bool = False,
        trigger_source: str = "manual",
        distiller_agent: ProviderCall | None = None,
        reviewer_agent: ProviderCall | None = None,
    ) -> WeeklyMemoryReport:
        current = now or local_now()
        run_key = _week_key(current)
        run_audit_id = await start_weekly_memory_run(self.db_path, run_key=run_key, trigger_source=trigger_source)
        cutoff = (current - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        try:
            await run_retention_cleanup(self.db_path, current)
            await backfill_canonical_memory(self.db_path)
            data = await self._collect(cutoff)
            summary = self._summarize(run_key, data, live=live and bool(distiller_agent))
            canonical_memory_ids = _canonical_memory_ids(data)
            confirmation_needed: tuple[str, ...] = ()
            provider_warning = ""
            canonical_saved = canonical_rejected = provider_calls = 0
            if live and distiller_agent:
                live_result = await live_weekly_canonical_distillation(
                    self.db_path,
                    run_key=run_key,
                    data=data,
                    distiller_agent=distiller_agent,
                    reviewer_agent=reviewer_agent,
                )
                canonical_saved = live_result.saved
                canonical_rejected = live_result.rejected
                provider_calls = live_result.provider_calls
                confirmation_needed = live_result.confirmation_needed
                provider_warning = live_result.reviewer_error
                canonical_memory_ids = tuple(dict.fromkeys((*canonical_memory_ids, *live_result.memory_ids)))
                summary = "\n".join((
                    summary,
                    f"Provider calls used: {provider_calls}.",
                    f"Live canonical memories saved: {canonical_saved}.",
                    f"Live canonical memories rejected: {canonical_rejected}.",
                    f"Claude confirmation needed: {len(confirmation_needed)}.",
                ))
                if provider_warning:
                    summary = "\n".join((
                        summary,
                        "Reviewer unavailable: no unreviewed canonical memories were saved.",
                    ))
            summary = "\n".join((
                summary,
                f"Canonical memory IDs used: {', '.join(canonical_memory_ids) if canonical_memory_ids else 'none'}.",
            ))
            source = "live_provider" if provider_calls else "dry_run"
            if save:
                await save_weekly_summary(
                    self.db_path,
                    run_key=run_key,
                    summary=summary,
                    source=source,
                    canonical_memory_ids=json.dumps(list(canonical_memory_ids)),
                )
            await finish_weekly_memory_run(
                self.db_path,
                run_id=run_audit_id,
                status="completed",
                summary_source=source if save else "not_saved",
                provider_calls=provider_calls,
                canonical_saved=canonical_saved,
                canonical_rejected=canonical_rejected,
                canonical_memory_ids=canonical_memory_ids,
                error=provider_warning,
            )
            return WeeklyMemoryReport(
                run_key,
                summary,
                save,
                run_audit_id,
                canonical_saved,
                canonical_rejected,
                provider_calls,
                canonical_memory_ids,
                confirmation_needed,
            )
        except Exception as exc:
            await finish_weekly_memory_run(
                self.db_path,
                run_id=run_audit_id,
                status="failed",
                error=f"{type(exc).__name__}: {exc}",
            )
            raise

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
                    SELECT memory_id, subject_key, content, confidence, source_channel
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
                    """
                    SELECT title, status, due_at, action_type
                    FROM tasks
                    WHERE COALESCE(retention_state, 'active') != 'deletion_pending'
                    ORDER BY updated_at DESC
                    LIMIT 12
                    """,
                ),
                "knowledge": await _fetch_all(
                    db,
                    "SELECT category, content FROM knowledge_base ORDER BY id DESC LIMIT 6",
                ),
            }

    @staticmethod
    def _summarize(run_key: str, data: dict[str, list[dict[str, str]]], live: bool = False) -> str:
        history = data["history"]
        preferences = [item for item in data["preferences"] if not _internal_preference(item.get("key", ""))]
        tasks = [item for item in data["tasks"] if item.get("action_type") not in INTERNAL_TASK_ACTIONS]
        open_tasks = [item for item in tasks if item.get("status") not in {"completed", "cancelled"}]
        completed = [item for item in tasks if item.get("status") == "completed"]
        lines = [
            f"Weekly memory {'live run' if live else 'dry run'} for {run_key}.",
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
        if not live:
            lines.append("Provider calls used: none. This is safe to run before live API keys.")
        return "\n".join(lines)




















async def _main() -> int:
    args = _args()
    await _init_weekly_job_db(args.db)
    distiller = weekly_distiller_agent() if args.live else None
    reviewer = weekly_reviewer_agent() if args.live else None
    report = await WeeklyMemoryDistiller(args.db).run(
        save=args.save,
        live=bool(distiller),
        trigger_source=args.trigger_source,
        distiller_agent=distiller,
        reviewer_agent=reviewer,
    )
    print(report.summary)
    print(f"saved: {'yes' if report.saved else 'no'}")
    print(f"live_provider: {'yes' if report.provider_calls else 'no'}")
    return 0


async def _init_weekly_job_db(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_weekly_memory_db(db_path)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run no-key weekly memory distillation.")
    parser.add_argument("--db", default="session_history.db", help="SQLite database path.")
    parser.add_argument("--save", action="store_true", help="Save the generated weekly summary.")
    parser.add_argument("--live", action="store_true", help="Use provider distillation when provider keys are available.")
    parser.add_argument("--trigger-source", default="manual", help="Audit source such as manual, launchd, or telegram.")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
