"""Approval-gated skill scaffold helpers.

Maya can notice missing abilities and offer to scaffold a skill, but scaffolding
is still an approval-gated lifecycle step. Plain "create a skill for X" queues a
confirmation; explicit approval phrasing such as "approve and scaffold the X
skill" creates the proposed skill file and test file through `SkillFactory`.

The proposed skill is stored but not activated. Activation remains separate and
requires review/test evidence so an unfinished skill cannot leak into normal
prompt context.
"""

from __future__ import annotations

import re

from maya_core.assistant_skill_helpers import queue_skill_scaffold
from maya_core.skill_factory import SkillFactory


async def handle_skill_creation_request(db_path: str, text: str, channel: str) -> str | None:
    subject = _skill_creation_subject(text)
    if not subject:
        return None
    return await queue_skill_scaffold(
        db_path,
        subject,
        channel,
        "I can draft a new skill scaffold for that gap. Do you want me to do it?",
    )


async def handle_explicit_skill_scaffold_approval(db_path: str, text: str) -> str | None:
    lowered = text.lower()
    if "skill" not in lowered:
        return None
    if not re.search(r"\b(?:approve|approved)\b|\bgo\s+ahead\b", lowered):
        return None
    subject = _explicit_skill_subject(text)
    if not subject:
        return None
    result = await SkillFactory(db_path).scaffold_skill(subject)
    return f"Done. I created the skill scaffold for {result['title']} at {result['scaffold_path']}."


def _skill_creation_subject(text: str) -> str:
    patterns = (
        r"^(?:create|make|draft)\s+(?:a\s+)?(?:proposed\s+)?skill\s+(?:for|to)\s+(.+)$",
        r"^(?:create|make|draft)\s+(?:a\s+)?(.+?)\s+skill(?:\s+first)?(?:\s+and\s+.+)?$",
    )
    for pattern in patterns:
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def _explicit_skill_subject(text: str) -> str:
    cleaned = " ".join(str(text or "").strip().split()).strip(" .")
    patterns = (
        r"^(?:approve(?:d)?\s+and\s+)?(?:scaffold|draft|create|make)\s+(?:the\s+|a\s+)?(.+?)\s+skill\s+(?:for|to)\s+(.+)$",
        r"^(?:approve(?:d)?\s+)?(?:the\s+|a\s+)?(.+?)\s+skill\s+(?:for|to)\s+(.+)$",
        r"^(?:go\s+ahead\s+and\s+)?(?:scaffold|draft|create|make)\s+(?:the\s+|a\s+)?(.+?)\s+skill$",
        r"^(?:approve(?:d)?\s+and\s+)?(?:scaffold|draft|create|make)\s+(?:a\s+)?skill\s+(?:for|to)\s+(.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, cleaned, re.IGNORECASE)
        if not match:
            continue
        parts = [part.strip(" .") for part in match.groups() if part and part.strip(" .")]
        subject = " ".join(parts)
        subject = re.sub(r"^(?:approve(?:d)?\s+and\s+|go\s+ahead\s+and\s+)", "", subject, flags=re.I)
        return subject.strip(" .")
    return ""
