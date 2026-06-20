from __future__ import annotations

from datetime import datetime, timezone


def activation_score(*, overlap: int, pinned: bool, reinforcement_count: int, updated_at: str | None) -> int:
    score = overlap * 10
    if pinned:
        # Pin guarantees *inclusion* (handled by the candidate rule in
        # search_relevant_canonical_memories), not top *ranking*. Kept below
        # a single token overlap (10) so any real lexical evidence outranks
        # an unrelated pinned rule; among zero-evidence rows pin still wins.
        # The old +30 let one pinned rule occupy the top slot for nearly
        # every query (recall@1 ~0 outside exact in the 2026-06-09 baseline).
        score += 6
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
