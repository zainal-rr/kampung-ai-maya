from __future__ import annotations

import json

from weekly_memory import WeeklyMemoryDistiller
from weekly_memory_providers import weekly_distiller_agent, weekly_reviewer_agent
from weekly_memory_store import latest_weekly_memory_runs, latest_weekly_summary


async def weekly_memory_status_text(db_path: str) -> str:
    runs = await latest_weekly_memory_runs(db_path, limit=5)
    latest = await latest_weekly_summary(db_path)
    lines = ["Weekly memory status:"]
    if latest:
        ids = _decode_ids(str(latest.get("canonical_memory_ids") or "[]"))
        lines.append(f"1) latest summary: {latest.get('run_key')} from {latest.get('source')} at {latest.get('created_at')}")
        lines.append(f"2) canonical memories used: {len(ids)}")
    else:
        lines.append("1) latest summary: none")
        lines.append("2) canonical memories used: 0")
    if not runs:
        lines.append("3) recent runs: none")
        return "\n".join(lines)
    lines.append("3) recent runs:")
    for index, run in enumerate(runs[:5], start=1):
        detail = (
            f"{index}. {run.get('run_key')} | {run.get('trigger_source')} | "
            f"{run.get('status')} | started {run.get('started_at')}"
        )
        if run.get("completed_at"):
            detail += f" | completed {run.get('completed_at')}"
        if run.get("error"):
            detail += f" | error: {run.get('error')}"
        lines.append(detail)
    return "\n".join(lines)


async def run_weekly_memory_now_text(db_path: str, trigger_source: str = "telegram") -> str:
    distiller = weekly_distiller_agent()
    reviewer = weekly_reviewer_agent()
    report = await WeeklyMemoryDistiller(db_path).run(
        save=True,
        live=bool(distiller),
        trigger_source=trigger_source,
        distiller_agent=distiller,
        reviewer_agent=reviewer,
    )
    source = "live provider" if report.provider_calls else "dry run"
    return (
        "Weekly memory run completed.\n"
        f"1) run: {report.run_key}\n"
        f"2) trigger: {trigger_source}\n"
        f"3) source: {source}\n"
        f"4) canonical memories used: {len(report.canonical_memory_ids)}\n"
        f"5) saved: {'yes' if report.saved else 'no'}"
    )


def _decode_ids(raw: str) -> list[str]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [str(item) for item in data if item]
