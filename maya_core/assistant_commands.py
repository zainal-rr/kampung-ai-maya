"""Top-level command router for non-model Maya actions.

`KampungAssistant` asks this router before falling back to normal model chat.
Each handler either returns a finished command response or `None`, allowing the
next handler/model lane to continue. This is where durable local actions such as
documents, memory lookup, skill lifecycle, safety gates, project mode, routines,
and workflow confirmations are sequenced.

Ordering matters. Approval/confirmation handlers run before broad workflow or
document handlers so stale approvals do not hijack unrelated turns, and private
exposure checks run first so secrets never reach downstream model/tool lanes.
"""

from __future__ import annotations

import re

from maya_core.assistant_context_helpers import handle_context_command
from maya_core.activation import handle_activation_command
from maya_core.assistant_command_helpers import direct_key
from maya_core.assistant_briefing_helpers import handle_weekly_reflection
from maya_core.assistant_confirmation_helpers import resolve_pending_confirmation
from maya_core.assistant_memory_commands import handle_memory_forget, handle_memory_lookup
from maya_core.assistant_schedule_commands import handle_reminder_command, handle_summary_task_command
from maya_core.assistant_skill_creation import handle_explicit_skill_scaffold_approval, handle_skill_creation_request
from maya_core.artisan_apply import apply_latest_artisan_repo_changes
from maya_core.artisan_runner import latest_artisan_summary_text, latest_artisan_transcript_text
from maya_documents.artifact_review_store import resolve_review_activity_text
from maya_core.assistant_task_helpers import create_sensitive_send_task, format_open_tasks, parse_task_delete_request
from maya_documents.document_actions import DocumentActionRouter
from maya_core.everyday_commands import EverydayCommandRouter
from maya_core.file_actions import FileActionRouter
from maya_core.drawing_actions import DrawingActionRouter
from maya_core.imac_workflows import ImacWorkflowRouter
from local_actions import LocalActionRouter
from memory_service import MemoryService
from permission_policy import contains_sensitive_info, hard_no_private_exposure_text, is_private_exposure
from presentation_command_helpers import handle_presentation_command
from project_actions import ProjectActionRouter
from routine_commands import RoutineCommandRouter
from safety_action_commands import safety_action_reply
from self_heal_commands import handle_self_heal_status
from session_memory_actions import handle_session_memory_command
from skill_registry import SkillRegistry
from maya_core.assistant_skill_commands import handle_skill_lifecycle, handle_skill_listing, handle_skill_proposals
from storage import cancel_matching_tasks, list_preferences, list_tasks
from unsupported_actions import unsupported_action_subject
from voice_session_commands import handle_voice_session_command
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
        self.workspace = WorkspaceActionRouter(db_path=db_path)
        self.drawing = DrawingActionRouter()
        self.projects = ProjectActionRouter(db_path)
        self.workflows = ImacWorkflowRouter(db_path)
        self.web = WebActionRouter()
        self.routines = RoutineCommandRouter(db_path)
        self.everyday = EverydayCommandRouter(db_path)
        self.last_lane = self.last_reason = ""
        self.last_cost_recorded = False

    async def handle(self, clean_text: str, channel: str) -> str | None:
        self.last_lane = self.last_reason = ""
        self.last_cost_recorded = False
        if is_private_exposure(clean_text):
            self.last_lane = "command"
            self.last_reason = "private exposure block"
            return hard_no_private_exposure_text()
        explicit_skill_approval = await self._handle_explicit_skill_scaffold_approval(clean_text, channel)
        if explicit_skill_approval is not None:
            self.last_lane = "command"
            self.last_reason = "explicit skill scaffold approval"
            return explicit_skill_approval
        workflow_confirmation = await self.workflows.handle_confirmation(clean_text)
        if workflow_confirmation is not None:
            self.last_lane = "command"
            self.last_reason = "workflow confirmation"
            return workflow_confirmation
        confirmation = await self._resolve_confirmation(clean_text, channel)
        if confirmation is not None:
            self.last_lane = "command"
            self.last_reason = "confirmation resolver"
            return confirmation

        for handler in (
            self._handle_reminder,
            self._handle_activation_command,
            self._handle_summary_task,
            self._handle_weekly_reflection,
            self._handle_safety_actions,
            self._handle_voice_session_command,
            self._handle_review_resolution,
            self._handle_everyday_commands,
            self._handle_skill_creation,
            self._handle_document_actions,
            self._handle_imac_workflows,
            self._handle_local_creation_actions,
            self._handle_project_actions,
            self._handle_web_actions,
            self._handle_local_actions,
            self._handle_routine_commands,
            self._handle_send_to_telegram,
            self._handle_task_deletion,
            self._handle_task_listing,
            self._handle_context_window,
            self._handle_artisan_status,
            self._handle_session_memory_command,
            self._handle_preference_listing,
            self._handle_skill_listing,
            self._handle_skill_proposals,
            self._handle_skill_lifecycle,
            self._handle_self_heal_status,
            self._handle_memory_forget,
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
        return await handle_reminder_command(self.db_path, text, channel)

    async def _handle_summary_task(self, text: str, channel: str) -> str | None:
        return await handle_summary_task_command(self.db_path, text, channel)

    async def _handle_weekly_reflection(self, text: str, channel: str) -> str | None:
        return await handle_weekly_reflection(self.db_path, text, channel)
    async def _handle_safety_actions(self, text: str, channel: str) -> str | None:
        reply = safety_action_reply(text)
        if reply:
            self.last_lane = "command"
            self.last_reason = "safety gate"
        return reply

    async def _handle_everyday_commands(self, text: str, channel: str) -> str | None:
        reply = await self.everyday.handle(text, channel)
        if reply:
            self.last_lane = self.everyday.last_lane
            self.last_reason = self.everyday.last_reason
        return reply
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
        presentation = await handle_presentation_command(self.db_path, text, channel)
        if presentation:
            reply, self.last_lane, self.last_reason, self.last_cost_recorded = presentation
            return reply
        reply = await self.documents.handle(text, channel)
        if reply and self.documents.last_model_lane:
            self.last_lane = self.documents.last_model_lane
            self.last_reason = "document workflow"
            self.last_cost_recorded = self.documents.last_cost_recorded
        return reply

    async def _handle_local_creation_actions(self, text: str, channel: str) -> str | None:
        return (
            await self.workspace.handle(text, channel)
            or await self.drawing.handle(text, channel)
            or await self.files.handle(text, channel)
        )

    async def _handle_project_actions(self, text: str, channel: str) -> str | None:
        reply = await self.projects.handle(text, channel)
        if reply:
            self.last_lane = "command"
            self.last_reason = "project mode"
        return reply

    async def _handle_imac_workflows(self, text: str, channel: str) -> str | None:
        return await self.workflows.handle(text, channel)

    async def _handle_web_actions(self, text: str, channel: str) -> str | None:
        return await self.web.handle(text, channel)

    async def _handle_routine_commands(self, text: str, channel: str) -> str | None:
        return await self.routines.handle(text, channel)

    async def _handle_skill_creation(self, text: str, channel: str) -> str | None:
        return await handle_skill_creation_request(self.db_path, text, channel)

    async def _handle_explicit_skill_scaffold_approval(self, text: str, channel: str) -> str | None:
        return await handle_explicit_skill_scaffold_approval(self.db_path, text)

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

    async def _handle_artisan_status(self, text: str, channel: str) -> str | None:
        key = direct_key(text)
        if key in {"what did artisan say", "show artisan status", "artisan status", "show artisan"}:
            self.last_lane = "command"
            self.last_reason = "artisan status"
            return await latest_artisan_summary_text(self.db_path)
        if key in {"show artisan transcript", "artisan transcript", "what was artisan transcript"}:
            self.last_lane = "command"
            self.last_reason = "artisan transcript"
            return await latest_artisan_transcript_text(self.db_path)
        if key in {"apply artisan changes", "apply latest artisan changes", "apply artisan repo changes"}:
            self.last_lane = "command"
            self.last_reason = "artisan apply approved changes"
            return await apply_latest_artisan_repo_changes(self.db_path)
        return None

    async def _handle_voice_session_command(self, text: str, channel: str) -> str | None:
        reply = await handle_voice_session_command(self.db_path, text)
        if reply:
            self.last_lane = "command"
            self.last_reason = "voice session review"
        return reply

    async def _handle_review_resolution(self, text: str, channel: str) -> str | None:
        reply = await resolve_review_activity_text(self.db_path, text)
        if reply:
            self.last_lane = "command"
            self.last_reason = "artifact review resolution"
        return reply

    async def _handle_session_memory_command(self, text: str, channel: str) -> str | None:
        reply = await handle_session_memory_command(self.db_path, text)
        if reply:
            self.last_lane = "command"
            self.last_reason = "session memory"
        return reply

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
        reply = await handle_self_heal_status(self.db_path, text)
        if reply:
            self.last_lane = "command"
            self.last_reason = "self-heal status"
        return reply

    async def _handle_memory_lookup(self, text: str, channel: str) -> str | None:
        reply = await handle_memory_lookup(self.memory, text)
        if reply:
            self.last_lane = "command"
            self.last_reason = "memory lookup"
        return reply

    async def _handle_memory_forget(self, text: str, channel: str) -> str | None:
        reply = await handle_memory_forget(self.db_path, text)
        if reply:
            self.last_lane = "command"
            self.last_reason = "memory forget"
        return reply

    async def _resolve_confirmation(self, text: str, channel: str) -> str | None:
        return await resolve_pending_confirmation(self.db_path, text, channel)
