from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass

import aiosqlite

from maya_core.skill_outcome_store import init_skill_outcome_db, recent_skill_outcomes
from maya_core.skill_store import init_skill_db, list_custom_skills, list_skill_proposals, latest_skill_usage


@dataclass(frozen=True)
class SkillReviewReport:
    summary: str
    saved: bool


async def init_skill_review_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS skill_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                summary TEXT NOT NULL,
                source TEXT DEFAULT 'dry_run',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


class WeeklySkillReviewer:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def run(self, save: bool = False) -> SkillReviewReport:
        await init_skill_db(self.db_path)
        await init_skill_outcome_db(self.db_path)
        data = {
            "skills": await list_custom_skills(self.db_path, limit=20),
            "proposals": await list_skill_proposals(self.db_path, limit=10),
            "usage": await latest_skill_usage(self.db_path, limit=20),
            "outcomes": await recent_skill_outcomes(self.db_path, limit=30),
        }
        summary = _summary(data)
        if save:
            await save_skill_review(self.db_path, summary)
        return SkillReviewReport(summary, save)


async def save_skill_review(db_path: str, summary: str, source: str = "dry_run") -> None:
    await init_skill_review_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO skill_reviews (summary, source) VALUES (?, ?)",
            (summary, source),
        )
        await db.commit()


async def latest_skill_review(db_path: str) -> str | None:
    await init_skill_review_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT summary FROM skill_reviews ORDER BY created_at DESC, id DESC LIMIT 1"
        )
        row = await cursor.fetchone()
    return str(row[0]) if row else None


def _summary(data: dict[str, list[dict[str, str]]]) -> str:
    outcomes = data["outcomes"]
    failures = [item for item in outcomes if item.get("outcome") == "failure"]
    corrections = [item for item in outcomes if item.get("outcome") == "user_corrected"]
    missing = [item for item in outcomes if item.get("missing_step")]
    disabled = [item for item in data["skills"] if item.get("status") == "disabled"]
    active = [item for item in data["skills"] if item.get("status") == "active"]
    proposals = data["proposals"]
    usage = data["usage"]
    used_ids = {item.get("skill_id") for item in usage}
    stale = [item for item in active if item.get("skill_id") not in used_ids]
    unsupported = [item for item in proposals if "Draft skill for:" in item.get("summary", "")]
    waiting = [item for item in proposals if item.get("status") in {"draft", "proposed"}]
    lines = [
        "Weekly skill review dry run.",
        f"Skills sampled: {len(data['skills'])}.",
        f"Recent skill selections: {len(usage)}.",
        f"Recent failures: {len(failures)}.",
        f"User corrections: {len(corrections)}.",
        f"Missing-step reports: {len(missing)}.",
        f"Open proposals sampled: {len(proposals)}.",
        f"Disabled skills sampled: {len(disabled)}.",
        f"Stale or unused active skills sampled: {len(stale)}.",
        f"Unsupported-action candidates sampled: {len(unsupported)}.",
        f"Proposals waiting for review: {len(waiting)}.",
        "Provider calls used: none.",
    ]
    lines.extend(_section("Most used skills", [item["name"] for item in usage[:3]]))
    lines.extend(_section("Skills needing improvement", [item["skill_id"] for item in failures[:3]]))
    lines.extend(_section("Skills with user corrections", [item["skill_id"] for item in corrections[:3]]))
    lines.extend(_section("Skills with missing steps", [item["skill_id"] for item in missing[:3]]))
    lines.extend(_section("Stale or unused skills", [item["name"] for item in stale[:3]]))
    lines.extend(_section("Skills to test", [item["skill_id"] for item in proposals[:3]]))
    lines.extend(_section("Skills to consider disabling", [item["name"] for item in disabled[:3]]))
    lines.extend(_section("New skill candidates", [item["request_text"] for item in proposals[:3]]))
    lines.append("No skills were edited, activated, disabled, or created by this review.")
    return "\n".join(lines)


def _section(title: str, values: list[str]) -> list[str]:
    clean = [value for value in values if value]
    return [f"{title}: {'; '.join(clean[:3]) if clean else 'none'}."]


async def _main() -> int:
    args = _args()
    report = await WeeklySkillReviewer(args.db).run(save=args.save)
    print(report.summary)
    print(f"saved: {'yes' if report.saved else 'no'}")
    return 0


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run no-key weekly skill review.")
    parser.add_argument("--db", default="session_history.db")
    parser.add_argument("--save", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
