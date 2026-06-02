from __future__ import annotations

from datetime import datetime, timezone


def activation_score(*, overlap: int, pinned: bool, reinforcement_count: int, updated_at: str | None) -> int:
    score = overlap * 10
    if pinned:
        score += 30
    score += min(max(reinforcement_count, 0), 10) * 2
    score -= min(_age_days(updated_at) // 30, 8)
    return score


def _age_days(value: str | None) -> int:
    if not value:
        return 0
    normalized = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            parsed = datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return 0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max((datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).days, 0)
