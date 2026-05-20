from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

from skill_library import ensure_skill_library, proposed_path, test_path
from skill_store import create_skill_proposal, upsert_skill
from skill_learning_store import upsert_skill_metadata


class SkillFactory:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.skill_dir = Path(os.getenv("MAYA_SKILL_DIR", "maya_skills"))
        ensure_skill_library(self.skill_dir)

    async def scaffold_skill(self, request_text: str) -> dict[str, str]:
        skill_id = self._slug(request_text)
        title = self._title(request_text)
        research_hint = self._research_hint(request_text)
        summary = f"Draft skill for: {request_text}"
        scaffold_path = str(proposed_path(skill_id, self.skill_dir).resolve())
        content = self._template(title, request_text, research_hint)

        await asyncio.to_thread(Path(scaffold_path).write_text, content, "utf-8")
        await asyncio.to_thread(test_path(skill_id, self.skill_dir).write_text, self._test_template(skill_id), "utf-8")
        await upsert_skill(
            self.db_path,
            skill_id=skill_id,
            name=title,
            description=summary,
            safety="sensitive",
            approval_mode="chat_confirmation",
            status="proposed",
            source="maya_scaffold",
            scaffold_path=scaffold_path,
        )
        await upsert_skill_metadata(
            self.db_path,
            skill_id,
            triggers=[request_text],
            non_triggers=["normal chat", "unrelated tasks"],
            tools_needed=["to be reviewed"],
            provider_lane="maya_runtime",
            safety_boundary="approval required before activation or external-code adoption",
            test_commands=[f"test skill {skill_id}"],
            review_notes="Needs Claude-style quality review before activation.",
        )
        proposal_id = await create_skill_proposal(
            self.db_path,
            skill_id=skill_id,
            request_text=request_text,
            summary=summary,
            research_hint=research_hint,
            scaffold_path=scaffold_path,
        )
        return {
            "skill_id": skill_id,
            "title": title,
            "proposal_id": str(proposal_id),
            "scaffold_path": scaffold_path,
            "research_hint": research_hint,
        }

    @staticmethod
    def _slug(text: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
        return slug[:48] or "maya_skill_draft"

    @staticmethod
    def _title(text: str) -> str:
        cleaned = " ".join(text.strip().split())
        return cleaned[:80] if cleaned else "New Maya Skill"

    @staticmethod
    def _research_hint(text: str) -> str:
        lowered = text.lower()
        if "ui" in lowered or "design" in lowered:
            return "Research strong UI patterns, layout heuristics, and high-quality examples before implementation."
        if "telegram" in lowered:
            return "Review Telegram bot UX constraints and message/media delivery patterns."
        return "Research trusted references and implementation patterns before activating this skill."

    @staticmethod
    def _template(title: str, request_text: str, research_hint: str) -> str:
        return f"""# {title}

## Purpose
{request_text}

## Status
Proposed scaffold created by Maya. Human review required before activation.

## Learning State
- draft: rough idea captured
- proposed: scaffold exists and needs review
- approved: Zainal approved implementation work
- active: skill is wired into Maya
- disabled: skill is parked or unsafe

## Inputs
- User request
- Current channel context
- Relevant memory and preferences

## Outputs
- Proposed action plan
- Safe execution path
- Verification notes

## Trigger Phrases
- Define the natural phrases that should call this skill
- Define phrases that should not call this skill

## Safety
- Default mode: chat confirmation required
- Do not activate or self-install external code without explicit approval
- Stop before delete, deploy, payments, private exposure, sending, or external-code adoption

## Research Plan
{research_hint}

## Required Tools
- List local files, apps, APIs, browser access, or models needed

## Permission Boundary
- Safe actions:
- Confirmation actions:
- Hard no actions:

## Implementation Notes
- Define trigger phrases
- Define required tools and permissions
- Define success checks
- Define rollback or cancellation behavior

## Tests
- Unit or smoke test:
- Safety test:
- Regression test:

## Activation Checklist
- Reviewed by Zainal
- Tests pass
- Documentation updated
- Skill status changed to active only after approval
"""

    @staticmethod
    def _test_template(skill_id: str) -> str:
        return f"""# {skill_id} Skill Tests

- [ ] trigger
- [ ] non_trigger
- [ ] safety
- [ ] happy_path
- [ ] failure_path
- [ ] regression
- [ ] approval
"""
