from __future__ import annotations

import re

from assistant_context_helpers import handle_context_command
from activation import handle_activation_command
from assistant_command_helpers import direct_key, empty_preference_memory_reply, format_memory_reply, is_preference_query
from assistant_briefing_helpers import handle_weekly_reflection
from assistant_confirmation_helpers import resolve_pending_confirmation
from assistant_skill_helpers import queue_skill_scaffold
from assistant_task_helpers import create_sensitive_send_task, format_open_tasks, parse_task_delete_request
from document_actions import DocumentActionRouter
from everyday_commands import EverydayCommandRouter
from file_actions import FileActionRouter
from drawing_actions import DrawingActionRouter
from imac_workflows import ImacWorkflowRouter
from local_actions import LocalActionRouter
from memory_service import MemoryService
from permission_policy import contains_sensitive_info, hard_no_private_exposure_text, is_private_exposure
from project_actions import ProjectActionRouter
from routine_commands import RoutineCommandRouter
from self_heal_commands import handle_self_heal_status
from skill_registry import SkillRegistry
from assistant_skill_commands import handle_skill_lifecycle, handle_skill_listing, handle_skill_proposals
from storage import cancel_matching_tasks, create_task, list_preferences, list_tasks
from time_parser import extract_due_from_text, format_due_text
from unsupported_actions import unsupported_action_subject
from web_actions import WebActionRouter
from workspace_actions import WorkspaceActionRouter


class AssistantCommandRouter:
    def __init__(self, db_path: str, memory: MemoryService, skills: SkillRegistry):
        self.db_path = db_path
        self.memory = memory
        self.skills = skills
        self.actions = LocalActionRouter()
        self.documents = DocumentActionRouter(db_path)
        self.files = FileActionRouter()
        self.workspace = WorkspaceActionRouter()
        self.drawing = DrawingActionRouter()
        self.projects = ProjectActionRouter(db_path)
        self.workflows = ImacWorkflowRouter(db_path)
        self.web = WebActionRouter()
        self.routines = RoutineCommandRouter(db_path)
        self.everyday = EverydayCommandRouter(db_path)

    async def handle(self, clean_text: str, channel: str) -> str | None:
        if is_private_exposure(clean_text):
            return hard_no_private_exposure_text()
        workflow_confirmation = await self.workflows.handle_confirmation(clean_text)
        if workflow_confirmation is not None:
            return workflow_confirmation
        confirmation = await self._resolve_confirmation(clean_text, channel)
        if confirmation is not None:
            return confirmation

        for handler in (
            self._handle_reminder,
            self._handle_activation_command,
            self._handle_summary_task,
            self._handle_weekly_reflection,
            self._handle_everyday_commands,
            self._handle_document_actions,
            self._handle_imac_workflows,
            self._handle_local_creation_actions,
            self._handle_project_actions,
            self._handle_web_actions,
            self._handle_local_actions,
            self._handle_routine_commands,
            self._handle_send_to_telegram,
            self._handle_skill_creation,
            self._handle_task_deletion,
            self._handle_task_listing,
            self._handle_context_window,
            self._handle_preference_listing,
            self._handle_skill_listing,
            self._handle_skill_proposals,
            self._handle_skill_lifecycle,
            self._handle_self_heal_status,
            self._handle_memory_lookup,
            self._handle_unsupported_action,
        ):
            result = await handler(clean_text, channel)
            if result is not None:
                return result
        return None

    async def _handle_activation_command(self, text: str, channel: str) -> str | None:
        return await handle_activation_command(self.db_path, text)

    async def _handle_reminder(self, text: str, channel: str) -> str | None:
        match = re.match(r"^(?:remind me to|create task)\s+(.+)$", text, re.IGNORECASE)
        if not match:
            return None
        title, due_at = extract_due_from_text(match.group(1).strip())
        task_id = await create_task(
            self.db_path,
            title=title,
            details=text,
            channel=channel,
            action_type="follow_up",
            autonomy_mode="auto_safe",
            due_at=due_at,
        )
        return f"Got it. I saved task #{task_id}: {title}, {format_due_text(due_at)}."

    async def _handle_summary_task(self, text: str, channel: str) -> str | None:
        match = re.match(r"^(?:summarize my day|summarize my history|schedule summary)\s*(.*)$", text, re.IGNORECASE)
        if not match:
            return None
        title, due_at = extract_due_from_text(f"history summary {match.group(1).strip()}".strip())
        task_id = await create_task(
            self.db_path,
            title=title,
            details=text,
            channel=channel,
            action_type="summarize_history",
            autonomy_mode="auto_safe",
            due_at=due_at,
        )
        return f"Done. I scheduled summary task #{task_id}, {format_due_text(due_at)}."

    async def _handle_weekly_reflection(self, text: str, channel: str) -> str | None:
        return await handle_weekly_reflection(self.db_path, text, channel)

    async def _handle_everyday_commands(self, text: str, channel: str) -> str | None:
        return await self.everyday.handle(text, channel)

    async def _handle_send_to_telegram(self, text: str, channel: str) -> str | None:
        match = re.match(r"^(?:send|share)\s+(.+?)\s+to telegram$", text, re.IGNORECASE)
        if not match:
            return None
        if contains_sensitive_info(match.group(1)):
            return hard_no_private_exposure_text()
        return await create_sensitive_send_task(
            self.db_path,
            match.group(1).strip(),
            channel,
            "send_message",
        )

    async def _handle_local_actions(self, text: str, channel: str) -> str | None:
        return await self.actions.handle(text)

    async def _handle_document_actions(self, text: str, channel: str) -> str | None:
        return await self.documents.handle(text, channel)

    async def _handle_local_creation_actions(self, text: str, channel: str) -> str | None:
        return (
            await self.workspace.handle(text, channel)
            or await self.drawing.handle(text, channel)
            or await self.files.handle(text, channel)
        )

    async def _handle_project_actions(self, text: str, channel: str) -> str | None:
        return await self.projects.handle(text, channel)

    async def _handle_imac_workflows(self, text: str, channel: str) -> str | None:
        return await self.workflows.handle(text, channel)

    async def _handle_web_actions(self, text: str, channel: str) -> str | None:
        return await self.web.handle(text, channel)

    async def _handle_routine_commands(self, text: str, channel: str) -> str | None:
        return await self.routines.handle(text, channel)

    async def _handle_skill_creation(self, text: str, channel: str) -> str | None:
        match = re.match(r"^(?:create|make|draft)\s+(?:a\s+)?skill\s+(?:for|to)\s+(.+)$", text, re.IGNORECASE)
        if not match:
            return None
        subject = match.group(1).strip()
        return await queue_skill_scaffold(
            self.db_path,
            subject,
            channel,
            "I can draft a new skill scaffold for that gap. Do you want me to do it?",
        )

    async def _handle_unsupported_action(self, text: str, channel: str) -> str | None:
        subject = unsupported_action_subject(text)
        if subject is None:
            return None
        return await queue_skill_scaffold(
            self.db_path,
            subject,
            channel,
            "I don't have a real skill for that yet. Do you want me to draft the missing skill first?",
        )

    async def _handle_task_deletion(self, text: str, channel: str) -> str | None:
        request = parse_task_delete_request(text)
        if request is None:
            return None
        task_id, query = request
        matches = await cancel_matching_tasks(self.db_path, query=query, task_id=task_id)
        if not matches:
            return "I could not find an open task matching that."
        if len(matches) == 1:
            return f"Done. I removed task #{matches[0]['id']} from your open tasks."
        return f"Done. I removed {len(matches)} open tasks."

    async def _handle_task_listing(self, text: str, channel: str) -> str | None:
        if direct_key(text) not in {"what are my tasks", "list my tasks", "show my tasks"}:
            return None
        return format_open_tasks(await list_tasks(self.db_path, limit=5))

    async def _handle_context_window(self, text: str, channel: str) -> str | None:
        return await handle_context_command(self.db_path, text)

    async def _handle_preference_listing(self, text: str, channel: str) -> str | None:
        if direct_key(text) not in {
            "show my preferences", "list my preferences", "tell me my preference",
            "tell me my preferences", "what are my preferences", "what is my preference",
        }:
            return None
        preferences = await list_preferences(self.db_path, limit=5)
        preferences = [item for item in preferences if "chat_id" not in item["key"].lower()]
        if not preferences:
            return "I don't have any stored preference notes yet."
        return "Here's what I have for your preferences:\n" + "\n".join(
            f"- {item['value']}" for item in preferences
        )

    async def _handle_skill_listing(self, text: str, channel: str) -> str | None:
        return await handle_skill_listing(self.db_path, self.skills, text)

    async def _handle_skill_proposals(self, text: str, channel: str) -> str | None:
        return await handle_skill_proposals(self.db_path, text)

    async def _handle_skill_lifecycle(self, text: str, channel: str) -> str | None:
        return await handle_skill_lifecycle(self.db_path, text)

    async def _handle_self_heal_status(self, text: str, channel: str) -> str | None:
        return await handle_self_heal_status(self.db_path, text)

    async def _handle_memory_lookup(self, text: str, channel: str) -> str | None:
        match = re.match(r"^(?:what do you remember about|search memory for|show memory about)\s+(.+)$", text, re.IGNORECASE)
        if not match:
            return None
        query = match.group(1).strip()
        preference_query = is_preference_query(query)
        if preference_query:
            snippets = await self.memory.search_preferences(query, limit=6)
            if not snippets:
                return empty_preference_memory_reply(query)
        else:
            snippets = await self.memory.search(query, limit=6)
        if not snippets:
            return "I don't have that saved in memory yet."
        return format_memory_reply(query, snippets, preference_query)

    async def _resolve_confirmation(self, text: str, channel: str) -> str | None:
        return await resolve_pending_confirmation(self.db_path, text, channel)
