from __future__ import annotations

import re


def verified_learning_message(kind: str, verified: bool) -> str:
    if not verified:
        return "I cannot say I learned it yet because the write was not verified."
    if kind == "preference":
        return "I learned and saved a preference."
    if kind == "skill_proposal":
        return "I updated a skill proposal."
    if kind == "active_skill":
        return "I improved an active skill after approval, tests, and activation."
    return "I recorded the learning update."


def approval_needed_message() -> str:
    return "I cannot improve this yet because I need approval."


def failure_notice(skill_name: str, count: int) -> str:
    return f"I noticed {skill_name} failed {count} times."


def blocks_vague_claim(text: str) -> bool:
    lowered = " ".join(text.lower().split())
    vague = ("i'll remember that", "i improved myself", "skill updated")
    return any(marker in lowered for marker in vague)


def enforce_honest_claims(text: str) -> str:
    replacements = {
        r"\bi'll remember that\b": "I can save that after verifying the write",
        r"\bi improved myself\b": "I can propose an improvement for review",
        r"\bskill updated\b": "Skill proposal noted",
    }
    cleaned = text
    for pattern, honest in replacements.items():
        cleaned = re.sub(pattern, honest, cleaned, flags=re.IGNORECASE)
    return cleaned
