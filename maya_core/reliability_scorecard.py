from __future__ import annotations

from dataclasses import dataclass

from live_reliability_soak import SoakDay, load_soak, soak_summary


@dataclass(frozen=True)
class ReliabilityScorecard:
    days_recorded: int
    coverage_percent: float
    readiness_score: float
    total_failures: int
    telegram_success: float | None
    imac_voice_success: float | None
    file_delivery_success: float | None
    browser_success: float | None
    memory_accuracy: float | None
    route_accuracy: float | None
    uptime_percent: float | None
    status: str


FAILURE_KEYS = (
    "missed_replies",
    "wrong_routes",
    "voice_timeouts",
    "memory_mistakes",
    "file_delivery_failures",
    "browser_failures",
    "cost_spikes",
    "false_saved_claims",
    "user_corrections",
)


def reliability_scorecard(days: list[SoakDay] | None = None) -> ReliabilityScorecard:
    rows = (days if days is not None else load_soak())[-30:]
    summary = soak_summary(rows, window_days=30)
    failures = sum(int(summary[key]) for key in FAILURE_KEYS)
    rates = [
        _rate(summary["telegram_replies"], summary["missed_replies"]),
        _rate(summary["imac_voice_turns"], summary["voice_timeouts"]),
        _rate(summary["file_deliveries"], summary["file_delivery_failures"]),
        _rate(summary["browser_workflows"], summary["browser_failures"]),
        _rate(summary["memory_ops"], summary["memory_mistakes"] + summary["false_saved_claims"]),
        _route_rate(summary),
        _uptime_rate(summary),
    ]
    available = [rate for rate in rates if rate is not None]
    coverage = min(1.0, int(summary["days_recorded"]) / 30)
    rate_score = sum(available) / len(available) if available else 0
    readiness = round(((coverage * 0.35) + (rate_score * 0.65)) * 100, 1)
    status = _status(int(summary["days_recorded"]), failures, readiness)
    return ReliabilityScorecard(
        int(summary["days_recorded"]),
        round(coverage * 100, 1),
        readiness,
        failures,
        rates[0],
        rates[1],
        rates[2],
        rates[3],
        rates[4],
        rates[5],
        rates[6],
        status,
    )


def format_reliability_scorecard(days: list[SoakDay] | None = None) -> str:
    card = reliability_scorecard(days)
    lines = [
        "30-day reliability scorecard:",
        f"1) status: {card.status}",
        f"2) evidence coverage: {card.days_recorded}/30 days ({card.coverage_percent}%)",
        f"3) readiness score: {card.readiness_score}/100",
        f"4) total failure/correction events: {card.total_failures}",
        f"5) Telegram reply success: {_pct(card.telegram_success)}",
        f"6) iMac voice success: {_pct(card.imac_voice_success)}",
        f"7) file delivery success: {_pct(card.file_delivery_success)}",
        f"8) browser workflow success: {_pct(card.browser_success)}",
        f"9) memory accuracy: {_pct(card.memory_accuracy)}",
        f"10) route accuracy: {_pct(card.route_accuracy)}",
        f"11) uptime: {_pct(card.uptime_percent)}",
    ]
    return "\n".join(lines)


def _route_rate(summary: dict) -> float | None:
    total = sum(int(summary[key]) for key in ("telegram_replies", "imac_voice_turns", "browser_workflows", "file_deliveries", "memory_ops"))
    return _rate(total, int(summary["wrong_routes"]))


def _uptime_rate(summary: dict) -> float | None:
    days = int(summary["days_recorded"])
    if not days:
        return None
    return min(1.0, float(summary["uptime_minutes"]) / (days * 1440))


def _rate(total: int | float, failures: int | float) -> float | None:
    if total <= 0:
        return None
    return max(0.0, min(1.0, (float(total) - float(failures)) / float(total)))


def _pct(value: float | None) -> str:
    return "no data" if value is None else f"{round(value * 100, 1)}%"


def _status(days: int, failures: int, score: float) -> str:
    if days < 7:
        return "insufficient-data"
    if days < 30:
        return "soak-in-progress"
    if failures == 0 and score >= 95:
        return "30-day-pass"
    return "needs-review"


def main() -> None:
    print(format_reliability_scorecard())


if __name__ == "__main__":
    main()
