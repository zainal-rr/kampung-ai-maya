from __future__ import annotations

from pathlib import Path

from maya_core.repo_paths import repo_root
from maya_core.skill_store import init_skill_db, record_skill_usage, upsert_skill
from maya_travel.travel_booking_safety import travel_booking_safety_footer


async def record_stay_skill(db_path: str, skill_id: str, name: str, description: str, question: str) -> None:
    await init_skill_db(db_path)
    scaffold = repo_root(__file__) / "maya_skills" / "active" / f"{skill_id}.md"
    await upsert_skill(db_path, skill_id, name, description, "bounded", "policy_guard", "active", "local", str(scaffold))
    await record_skill_usage(
        db_path,
        skill_id=skill_id,
        name=name,
        query=question,
        lane="iMac stay_booking_skill",
        reason="stay booking intent routed to executable skill",
    )


def stay_workflow_value(provider: str, details) -> str:
    return (
        f"{provider}:location={details.location};checkin={details.checkin};"
        f"checkout={details.checkout};adults={details.adults};rooms={details.rooms}"
    )


def stay_reply(result) -> str:
    details = result.details
    lines = [
        f"{result.provider} skill used.",
        f"status: {'ready for review' if result.verified() else 'needs manual check'}",
        f"url: {result.url}",
        f"location: {details.location}",
        f"checkin: {details.checkin.isoformat()}",
        f"checkout: {details.checkout.isoformat()}",
        f"guests: {details.adults} adult{'s' if details.adults != 1 else ''}",
        f"rooms: {details.rooms}",
    ]
    if details.assumptions:
        lines.append("assumptions:")
        lines.extend(f"{idx}) {item}" for idx, item in enumerate(details.assumptions, 1))
    if result.options:
        lines.append("visible stay options:")
        lines.extend(f"{idx}) {item}" for idx, item in enumerate(result.options, 1))
    else:
        lines.append("visible stay options: none extracted from page text; use screenshot fallback if prices are visibly shown.")
    if not result.verified():
        lines.append("manual check needed: I opened the structured search, but the visible page did not clearly verify the search result state.")
    lines.append(travel_booking_safety_footer(len(result.options)))
    return "\n".join(lines)
