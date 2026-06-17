from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, replace
from datetime import UTC, date, datetime
from pathlib import Path

from maya_harness.live_reliability_collectors import infer_reliability_counts


SOAK_PATH = Path("logs") / "live_tests" / "reliability_soak.json"
AUTO_RECORD_NOTE = (
    "auto-counted from voice-session and controller logs; subjective failures/corrections need manual notes"
)


@dataclass(frozen=True)
class SoakDay:
    day: str
    telegram_replies: int = 0
    imac_voice_turns: int = 0
    file_deliveries: int = 0
    browser_workflows: int = 0
    memory_ops: int = 0
    workflow_recoveries: int = 0
    uptime_minutes: int = 0
    estimated_cost_usd: float = 0
    missed_replies: int = 0
    wrong_routes: int = 0
    voice_timeouts: int = 0
    memory_mistakes: int = 0
    file_delivery_failures: int = 0
    browser_failures: int = 0
    cost_spikes: int = 0
    false_saved_claims: int = 0
    user_corrections: int = 0
    notes: str = ""


def load_soak(path: Path = SOAK_PATH) -> list[SoakDay]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text("utf-8"))
        return [SoakDay(**item) for item in payload.get("days", [])]
    except (json.JSONDecodeError, TypeError):
        return []


def save_soak(days: list[SoakDay], path: Path = SOAK_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"updated_at": _now(), "days": [asdict(day) for day in days]}
    path.write_text(json.dumps(payload, indent=2), "utf-8")


def record_soak_day(day: SoakDay, path: Path = SOAK_PATH) -> None:
    rows = [row for row in load_soak(path) if row.day != day.day]
    rows.append(day)
    rows.sort(key=lambda item: item.day)
    save_soak(rows[-30:], path)


def infer_soak_day(
    day: date,
    *,
    repo_root: Path = Path("."),
    maya_root: Path = Path.home() / "Desktop" / "Maya",
    notes: str = "",
) -> SoakDay:
    counts = infer_reliability_counts(day, repo_root=repo_root, maya_root=maya_root)
    combined_notes = AUTO_RECORD_NOTE if not notes else f"{AUTO_RECORD_NOTE}; {notes}"
    return SoakDay(
        day=day.isoformat(),
        imac_voice_turns=counts.imac_voice_turns,
        file_deliveries=counts.file_deliveries,
        browser_workflows=counts.browser_workflows,
        uptime_minutes=counts.uptime_minutes,
        voice_timeouts=counts.voice_timeouts,
        file_delivery_failures=counts.file_delivery_failures,
        browser_failures=counts.browser_failures,
        notes=combined_notes,
    )


def soak_summary(days: list[SoakDay] | None = None, *, window_days: int = 7) -> dict[str, int | bool | float]:
    rows = (days if days is not None else load_soak())[-window_days:]
    totals = {
        "days_recorded": len(rows),
        "telegram_replies": sum(day.telegram_replies for day in rows),
        "imac_voice_turns": sum(day.imac_voice_turns for day in rows),
        "file_deliveries": sum(day.file_deliveries for day in rows),
        "browser_workflows": sum(day.browser_workflows for day in rows),
        "memory_ops": sum(day.memory_ops for day in rows),
        "workflow_recoveries": sum(day.workflow_recoveries for day in rows),
        "uptime_minutes": sum(day.uptime_minutes for day in rows),
        "estimated_cost_usd": round(sum(day.estimated_cost_usd for day in rows), 2),
        "missed_replies": sum(day.missed_replies for day in rows),
        "wrong_routes": sum(day.wrong_routes for day in rows),
        "voice_timeouts": sum(day.voice_timeouts for day in rows),
        "memory_mistakes": sum(day.memory_mistakes for day in rows),
        "file_delivery_failures": sum(day.file_delivery_failures for day in rows),
        "browser_failures": sum(day.browser_failures for day in rows),
        "cost_spikes": sum(day.cost_spikes for day in rows),
        "false_saved_claims": sum(day.false_saved_claims for day in rows),
        "user_corrections": sum(day.user_corrections for day in rows),
    }
    failure_keys = {
        "missed_replies",
        "wrong_routes",
        "voice_timeouts",
        "memory_mistakes",
        "file_delivery_failures",
        "browser_failures",
        "cost_spikes",
        "false_saved_claims",
        "user_corrections",
    }
    totals["seven_day_complete"] = totals["days_recorded"] >= 7
    totals["clean_soak"] = all(totals[key] == 0 for key in failure_keys)
    return totals


def format_soak_status(days: list[SoakDay] | None = None) -> str:
    summary = soak_summary(days)
    lines = [
        "7-day reliability soak:",
        f"1) days recorded: {summary['days_recorded']}/7",
        f"2) complete: {'yes' if summary['seven_day_complete'] else 'no'}",
        f"3) clean: {'yes' if summary['clean_soak'] else 'no'}",
    ]
    for key in (
        "missed_replies",
        "wrong_routes",
        "voice_timeouts",
        "memory_mistakes",
        "file_delivery_failures",
        "browser_failures",
        "cost_spikes",
        "false_saved_claims",
    ):
        lines.append(f"- {key}: {summary[key]}")
    return "\n".join(lines)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--record-today", action="store_true")
    parser.add_argument("--auto-record-today", action="store_true")
    parser.add_argument("--auto-record-day")
    parser.add_argument("--telegram-replies", type=int, default=0)
    parser.add_argument("--imac-voice-turns", type=int, default=0)
    parser.add_argument("--file-deliveries", type=int, default=0)
    parser.add_argument("--browser-workflows", type=int, default=0)
    parser.add_argument("--memory-ops", type=int, default=0)
    parser.add_argument("--workflow-recoveries", type=int, default=0)
    parser.add_argument("--uptime-minutes", type=int, default=0)
    parser.add_argument("--estimated-cost-usd", type=float, default=0)
    parser.add_argument("--missed-replies", type=int, default=0)
    parser.add_argument("--wrong-routes", type=int, default=0)
    parser.add_argument("--voice-timeouts", type=int, default=0)
    parser.add_argument("--memory-mistakes", type=int, default=0)
    parser.add_argument("--file-delivery-failures", type=int, default=0)
    parser.add_argument("--browser-failures", type=int, default=0)
    parser.add_argument("--cost-spikes", type=int, default=0)
    parser.add_argument("--false-saved-claims", type=int, default=0)
    parser.add_argument("--user-corrections", type=int, default=0)
    parser.add_argument("--notes", default="")
    args = parser.parse_args()
    if args.auto_record_today or args.auto_record_day:
        target_day = date.today() if args.auto_record_today else date.fromisoformat(args.auto_record_day)
        record_soak_day(_apply_cli_overrides(infer_soak_day(target_day, notes=args.notes), args))
    elif args.record_today:
        record_soak_day(_manual_day_from_args(args))
    print(format_soak_status())


def _manual_day_from_args(args: argparse.Namespace) -> SoakDay:
    return SoakDay(
        day=date.today().isoformat(),
        telegram_replies=args.telegram_replies,
        imac_voice_turns=args.imac_voice_turns,
        file_deliveries=args.file_deliveries,
        browser_workflows=args.browser_workflows,
        memory_ops=args.memory_ops,
        workflow_recoveries=args.workflow_recoveries,
        uptime_minutes=args.uptime_minutes,
        estimated_cost_usd=args.estimated_cost_usd,
        missed_replies=args.missed_replies,
        wrong_routes=args.wrong_routes,
        voice_timeouts=args.voice_timeouts,
        memory_mistakes=args.memory_mistakes,
        file_delivery_failures=args.file_delivery_failures,
        browser_failures=args.browser_failures,
        cost_spikes=args.cost_spikes,
        false_saved_claims=args.false_saved_claims,
        user_corrections=args.user_corrections,
        notes=args.notes,
    )


def _apply_cli_overrides(day: SoakDay, args: argparse.Namespace) -> SoakDay:
    return replace(
        day,
        telegram_replies=day.telegram_replies + args.telegram_replies,
        imac_voice_turns=day.imac_voice_turns + args.imac_voice_turns,
        file_deliveries=day.file_deliveries + args.file_deliveries,
        browser_workflows=day.browser_workflows + args.browser_workflows,
        memory_ops=day.memory_ops + args.memory_ops,
        workflow_recoveries=day.workflow_recoveries + args.workflow_recoveries,
        uptime_minutes=day.uptime_minutes + args.uptime_minutes,
        estimated_cost_usd=day.estimated_cost_usd + args.estimated_cost_usd,
        missed_replies=day.missed_replies + args.missed_replies,
        wrong_routes=day.wrong_routes + args.wrong_routes,
        voice_timeouts=day.voice_timeouts + args.voice_timeouts,
        memory_mistakes=day.memory_mistakes + args.memory_mistakes,
        file_delivery_failures=day.file_delivery_failures + args.file_delivery_failures,
        browser_failures=day.browser_failures + args.browser_failures,
        cost_spikes=day.cost_spikes + args.cost_spikes,
        false_saved_claims=day.false_saved_claims + args.false_saved_claims,
        user_corrections=day.user_corrections + args.user_corrections,
    )


if __name__ == "__main__":
    main()
