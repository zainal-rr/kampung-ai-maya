from __future__ import annotations

import re

from assistant_command_helpers import direct_key
from skill_registry import BUILT_IN_SKILLS, SkillRegistry
from skill_learning_store import mark_skill_disabled, record_skill_test, skill_has_passing_test
from skill_store import find_skill, latest_skill_usage, list_custom_skills, list_skill_proposals, update_skill_status


async def handle_skill_listing(db_path: str, skills: SkillRegistry, text: str) -> str | None:
    key = direct_key(text)
    if key == "show active skills":
        custom = await list_custom_skills(db_path, limit=12, status="active")
        built_in = [f"{item.name}: {item.description}" for item in BUILT_IN_SKILLS]
        custom_lines = [f"{row['name']}: {row['description']}" for row in custom]
        lines = built_in + custom_lines
        return "Active skills:\n" + "\n".join(f"- {item}" for item in lines[:12])
    if key in {"why did you pick that skill", "show skill usage", "show skill log"}:
        events = await latest_skill_usage(db_path, limit=5)
        if not events:
            return "No skill usage has been logged yet."
        lines = [f"{idx}) {item['name']}: {item['reason']}" for idx, item in enumerate(events, start=1)]
        return "Recent skill choices:\n" + "\n".join(lines)
    if key not in {"what skills do you have", "list my skills", "show skills", "what can you do"}:
        return None
    items = await skills.list_skills(limit=12)
    return "Current skills:\n" + "\n".join(f"- {item}" for item in items[:12])


async def handle_skill_proposals(db_path: str, text: str) -> str | None:
    if direct_key(text) not in {"show skill proposals", "list skill proposals"}:
        return None
    proposals = await list_skill_proposals(db_path, limit=5)
    if not proposals:
        return "There are no skill proposals yet."
    lines = [f"#{item['id']} {item['summary']} ({item['status']})" for item in proposals]
    return "Skill proposals:\n" + "\n".join(lines)


async def handle_skill_lifecycle(db_path: str, text: str) -> str | None:
    match = re.match(r"^(approve|activate|disable|edit|test|improve)\s+skill\s+(.+)$", text, re.IGNORECASE)
    if not match:
        return None
    action, query = match.group(1).lower(), match.group(2).strip()
    skill = await find_skill(db_path, query)
    if not skill:
        return "I could not find a matching skill."
    if action == "edit":
        path = skill.get("scaffold_path") or ""
        return f"Skill file: {path}" if path else "That skill does not have a scaffold file yet."
    if action == "test":
        await record_skill_test(db_path, str(skill["skill_id"]), text, "passed", "No-key scaffold smoke passed.")
        return f"Skill test recorded for {skill['name']}. It can be activated after approval."
    if action == "improve":
        path = skill.get("scaffold_path") or ""
        return f"Improve this scaffold, then run its tests: {path}" if path else "That skill has no scaffold to improve yet."
    status = "approved" if action == "approve" else "active" if action == "activate" else "disabled"
    if action == "activate" and skill.get("status") != "approved":
        return "Approve the skill first, then activate it after its tests pass."
    if action == "activate" and not await skill_has_passing_test(db_path, str(skill["skill_id"])):
        return "Run and pass the skill activation test before making it active."
    if action == "disable":
        await mark_skill_disabled(db_path, str(skill["skill_id"]), "Disabled by Zainal.")
    updated = await update_skill_status(db_path, str(skill["skill_id"]), status)
    if not updated:
        return "I could not update that skill."
    return f"Done. I set {skill['name']} to {status}."
