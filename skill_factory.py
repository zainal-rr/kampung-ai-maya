from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

from skill_library import ensure_skill_library, proposed_path, test_path
from skill_store import create_skill_proposal, upsert_skill
from skill_learning_store import upsert_skill_metadata
from security_manifest import SecurityManifest, upsert_manifest


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
        await upsert_manifest(
            self.db_path,
            SecurityManifest(
                "skill",
                skill_id,
                {"create_artifacts": True},
                hard_blocks=["private_exposure", "secrets", "auto_activation"],
                notes="Generated skill scaffold. Fill in exact permissions before activation.",
            ),
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
        safe_action = f"use this skill only when Zainal asks for: {request_text}"
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
- success: Maya completes the allowed read-only or local-planning portion and explains the useful next step.

## Trigger Phrases
- trigger: {request_text}
- trigger: use this skill to help with {title.lower()}
- trigger: handle a request where Zainal asks Maya to {title.lower()}
- non-trigger: normal chat that only mentions the topic but does not ask Maya to act
- non-trigger: unrelated document, memory, coding, or local file requests

## Safety
- Default mode: read-only or local planning unless the runtime permission policy allows more
- confirmation: browser clicks that submit, upload, send, purchase, book, comment, subscribe, like, delete, deploy, install, or change account state
- hard no: passwords, OTPs, API keys, tokens, bank/card data, private keys, hidden account data, or private exposure

## Research Plan
{research_hint}

## Required Tools
- Maya router and active channel context
- Existing local tools that already match this request
- Browser or file tools only when the permission policy allows them
- The Steward review lane when judgement, safety, or quality is uncertain

## Permission Boundary
- Safe actions: {safe_action}; inspect public or local information when requested; summarize options; recommend next steps
- Confirmation actions: external sends, account actions, browser form submissions, uploads, bookings, purchases, payments, installs, deploys, repo writes, restarts, deletes
- Hard no actions: reveal or handle secrets, OTPs, passwords, card/bank data, private keys, tokens, or identity documents

## Implementation Notes
- Select this skill only when the request directly matches the trigger intent.
- Keep proposed and approved-but-untested versions out of active prompts.
- happy path: understand the request, use allowed tools, summarize useful findings, recommend the next safe action, and record any artifact or workflow evidence.
- failure path: explain the blocker, cancel safely, and do not perform restricted actions.
- rollback: leave external state unchanged and close or pause any workflow without submitting, sending, deleting, or purchasing.

## Tests
- happy path: a matching request selects the skill and produces a useful recommendation or action plan.
- safety test: requests involving secrets, payments, account changes, delete, deploy, send, upload, booking, or final submit pause or hard-block.
- regression: unrelated requests do not select this skill.
- expected: the skill appears in prompt context only after approval, passing tests, and activation.

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
