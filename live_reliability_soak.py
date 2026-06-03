from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path


SOAK_PATH = Path("logs") / "live_tests" / "reliability_soak.json"


@dataclass(frozen=True)
class SoakDay:
    day: str
    missed_replies: int = 0
    wrong_routes: int = 0
    voice_timeouts: int = 0
    memory_mistakes: int = 0
    file_delivery_failures: int = 0
    browser_failures: int = 0
    cost_spikes: int = 0
    false_saved_claims: int = 0
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
    save_soak(rows[-7:], path)


def soak_summary(days: list[SoakDay] | None = None) -> dict[str, int | bool]:
    rows = days if days is not None else load_soak()
    totals = {
        "days_recorded": len(rows),
        "missed_replies": sum(day.missed_replies for day in rows),
        "wrong_routes": sum(day.wrong_routes for day in rows),
        "voice_timeouts": sum(day.voice_timeouts for day in rows),
        "memory_mistakes": sum(day.memory_mistakes for day in rows),
        "file_delivery_failures": sum(day.file_delivery_failures for day in rows),
        "browser_failures": sum(day.browser_failures for day in rows),
        "cost_spikes": sum(day.cost_spikes for day in rows),
        "false_saved_claims": sum(day.false_saved_claims for day in rows),
    }
    totals["seven_day_complete"] = totals["days_recorded"] >= 7
    totals["clean_soak"] = all(value == 0 for key, value in totals.items() if key not in {"days_recorded", "seven_day_complete", "clean_soak"})
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
    parser.add_argument("--missed-replies", type=int, default=0)
    parser.add_argument("--wrong-routes", type=int, default=0)
    parser.add_argument("--voice-timeouts", type=int, default=0)
    parser.add_argument("--memory-mistakes", type=int, default=0)
    parser.add_argument("--file-delivery-failures", type=int, default=0)
    parser.add_argument("--browser-failures", type=int, default=0)
    parser.add_argument("--cost-spikes", type=int, default=0)
    parser.add_argument("--false-saved-claims", type=int, default=0)
    parser.add_argument("--notes", default="")
    args = parser.parse_args()
    if args.record_today:
        record_soak_day(
            SoakDay(
                day=date.today().isoformat(),
                missed_replies=args.missed_replies,
                wrong_routes=args.wrong_routes,
                voice_timeouts=args.voice_timeouts,
                memory_mistakes=args.memory_mistakes,
                file_delivery_failures=args.file_delivery_failures,
                browser_failures=args.browser_failures,
                cost_spikes=args.cost_spikes,
                false_saved_claims=args.false_saved_claims,
                notes=args.notes,
            )
        )
    print(format_soak_status())


if __name__ == "__main__":
    main()
