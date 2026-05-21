from __future__ import annotations

from collections import defaultdict

from skill_outcome_store import recent_skill_outcomes
from skill_store import create_skill_proposal, list_custom_skills


async def analyze_skill_performance(db_path: str, threshold: int = 2) -> dict[str, list[str]]:
    outcomes = await recent_skill_outcomes(db_path, limit=200)
    success: dict[str, int] = defaultdict(int)
    failure: dict[str, int] = defaultdict(int)
    corrections: dict[str, int] = defaultdict(int)
    blocked: dict[str, int] = defaultdict(int)
    for row in outcomes:
        skill_id = str(row["skill_id"])
        outcome = str(row["outcome"])
        if outcome == "success":
            success[skill_id] += 1
        elif outcome == "failure":
            failure[skill_id] += 1
        elif outcome == "user_corrected":
            corrections[skill_id] += 1
        elif outcome == "blocked":
            blocked[skill_id] += 1
    proposals = []
    for skill_id, count in failure.items():
        if count >= threshold:
            proposals.append(await _proposal(db_path, skill_id, "Improve", f"{skill_id} failed {count} times."))
    for skill_id, count in success.items():
        if count >= threshold:
            proposals.append(await _proposal(db_path, skill_id, "Strengthen triggers", f"{skill_id} succeeded {count} times."))
    for skill_id, count in corrections.items():
        if count:
            proposals.append(await _proposal(db_path, skill_id, "Review correction", f"{skill_id} had {count} user correction."))
    for row in await list_custom_skills(db_path, status="active", limit=100):
        skill_id = str(row["skill_id"])
        if skill_id not in success and skill_id not in failure and skill_id not in corrections and skill_id not in blocked:
            proposals.append(await _proposal(db_path, skill_id, "Review stale skill", f"{skill_id} has no recent outcome evidence."))
    return {
        "success": [f"{k}:{v}" for k, v in sorted(success.items())],
        "failure": [f"{k}:{v}" for k, v in sorted(failure.items())],
        "corrections": [f"{k}:{v}" for k, v in sorted(corrections.items())],
        "blocked": [f"{k}:{v}" for k, v in sorted(blocked.items())],
        "proposals": proposals,
    }


async def skill_performance_text(db_path: str) -> str:
    result = await analyze_skill_performance(db_path)
    lines = ["Skill performance:"]
    for key in ("success", "failure", "corrections", "blocked", "proposals"):
        value = result.get(key) or []
        lines.append(f"{key}: {', '.join(value) if value else 'none'}")
    return "\n".join(lines)


async def _proposal(db_path: str, skill_id: str, action: str, summary: str) -> str:
    pid = await create_skill_proposal(
        db_path,
        skill_id,
        f"{action} {skill_id}",
        f"{summary} Do not change active behavior without approval.",
        "Record before and after tests before activation.",
    )
    return str(pid)
