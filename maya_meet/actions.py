from __future__ import annotations

import re
from dataclasses import dataclass

from maya_voice.work_control import revise_maya_work
from maya_voice.xai_realtime_work_tools import run_voice_browser_skill, start_maya_work


BROWSER_ACTION_RE = re.compile(
    r"\b(browser|chrome|google|search|look\s+up|open\s+(?:the\s+)?(?:page|site|url|link)|click|website|web)\b",
    re.IGNORECASE,
)
PUBLIC_BROWSER_ACTION_RE = re.compile(
    r"\b(?:google\s+search|search|look\s+up)\b|"
    r"\b(?:open|click)\s+(?:the\s+)?(?:"
    r"browser|"
    r"(?:first|second|third|\d+)(?:\s+(?:link|result))?|"
    r"result\s*\d+|"
    r"reddit(?:\s+(?:link|result|page))?|"
    r"tripadvisor(?:\s+(?:link|result|page))?|"
    r"public\s+(?:page|site|link)"
    r")\b",
    re.IGNORECASE,
)
PRIVATE_BROWSER_SURFACE_RE = re.compile(
    r"\b(private|logged[- ]?in|personal|my\s+(?:email|mail|gmail|calendar|drive|bank|account|messages?|dm|notes?|files?)|"
    r"gmail|inbox|mailbox|google\s+drive|docs\.google\.com|calendar\.google|bank|paypal|stripe|whatsapp|"
    r"facebook|instagram|linkedin|messages?|oauth|login|sign\s*in)\b",
    re.IGNORECASE,
)
PRIVATE_BROWSER_OPEN_RE = re.compile(r"\b(open|browser|chrome|site|page|url|link)\b", re.IGNORECASE)
ARTIFACT_ACTION_RE = re.compile(
    r"\b(word|document|doc|excel|spreadsheet|workbook|powerpoint|presentation|slides?|deck|pptx|xlsx|docx)\b",
    re.IGNORECASE,
)
CREATE_RE = re.compile(r"\b(make|create|build|draft|write|prepare|put together)\b", re.IGNORECASE)
REVISE_RE = re.compile(r"\b(revise|update|edit|add|change|append|fix|improve)\b", re.IGNORECASE)
DANGEROUS_ACTION_RE = re.compile(
    r"\b(delete|remove|erase|destroy|send|share|email|message|upload|export|overwrite|replace|submit|post|comment|"
    r"vote|like|subscribe|login|sign\s*in|oauth|pay|buy|purchase|book|reserve|transfer|archive|move|copy|"
    r"install|run|execute|command|terminal|repo|commit|push|deploy|restart|stop|start\s+service)\b",
    re.IGNORECASE,
)
ACTION_LIKE_RE = re.compile(
    r"^(?:please\s+)?(?:can\s+you\s+|could\s+you\s+|would\s+you\s+)?"
    r"(open|make|create|build|draft|write|prepare|revise|update|edit|add|change|append|fix|improve|"
    r"archive|share|send|delete|remove|export|upload|submit|run|execute|install|move|copy)\b",
    re.IGNORECASE,
)
APPROVAL_ATTEMPT_RE = re.compile(r"^(?:yes|yeah|yep|ok|okay|sure|approve|approved|go\s+ahead|do\s+it)\b", re.IGNORECASE)


@dataclass(frozen=True)
class MeetingActionExecution:
    status: str
    spoken: str
    reason_code: str


class MeetingActionRunner:
    def __init__(self, *, db_path: str, assistant=None):
        self.db_path = db_path
        self.assistant = assistant

    async def run(self, *, request: str, action_class: str, session_id: str = "") -> MeetingActionExecution:
        prompt = " ".join(str(request or "").split())
        if not prompt:
            return MeetingActionExecution("needs_clarification", "What should I do?", "empty_meeting_action")
        action = str(action_class or "").strip().lower()
        if action == "lookup":
            result = await run_voice_browser_skill(
                self.db_path,
                prompt,
                voice_session_id=session_id,
                short_ack="Meeting browser action",
            )
            return _meeting_spoken_result(result, completed="Done. I ran the browser action and left it open for you to check.")
        if action in {"draft", "scratch_artifact"}:
            if self.assistant is None:
                return MeetingActionExecution(
                    "failed",
                    "I can do meeting Office work only when the local work engine is attached.",
                    "meet_work_engine_unavailable",
                )
            if _looks_like_revision(prompt):
                result = await revise_maya_work(
                    self.db_path,
                    assistant=self.assistant,
                    voice_session_id=session_id,
                    content_revision=prompt,
                    channel="meet",
                )
                return _meeting_spoken_result(
                    result,
                    completed="Done. I captured the revision for the current Office artifact.",
                )
            result = await start_maya_work(
                self.db_path,
                prompt,
                assistant=self.assistant,
                voice_session_id=session_id,
                short_ack="Meeting Office action",
                kind="meet_artifact",
                tool_args={"request": prompt, "source": "meet_m2"},
                channel="meet",
            )
            return _meeting_spoken_result(
                result,
                completed="Done. I started the Office artifact and left it for you to check.",
            )
        return MeetingActionExecution(
            "failed",
            "I can only do reversible browser and Office artifact actions from a meeting.",
            "unsupported_meeting_action",
        )


def meeting_action_class(prompt: str) -> str:
    cleaned = " ".join(str(prompt or "").split())
    if not cleaned:
        return "answer"
    if APPROVAL_ATTEMPT_RE.search(cleaned):
        return "approval_attempt"
    if PRIVATE_BROWSER_SURFACE_RE.search(cleaned):
        return "private_lookup" if (BROWSER_ACTION_RE.search(cleaned) or PRIVATE_BROWSER_OPEN_RE.search(cleaned)) else "approval_required"
    if DANGEROUS_ACTION_RE.search(cleaned):
        return "approval_required"
    if PUBLIC_BROWSER_ACTION_RE.search(cleaned):
        return "lookup"
    if BROWSER_ACTION_RE.search(cleaned):
        return "private_lookup"
    if ARTIFACT_ACTION_RE.search(cleaned) and (CREATE_RE.search(cleaned) or REVISE_RE.search(cleaned)):
        return "scratch_artifact" if REVISE_RE.search(cleaned) else "draft"
    if ACTION_LIKE_RE.search(cleaned):
        return "unknown_action"
    return "answer"


def _looks_like_revision(prompt: str) -> bool:
    return bool(REVISE_RE.search(prompt) and ARTIFACT_ACTION_RE.search(prompt))


def _meeting_spoken_result(result: str, *, completed: str) -> MeetingActionExecution:
    status = _status_from_tool_result(result)
    if status == "completed":
        return MeetingActionExecution("completed", completed, "meeting_action_completed")
    if status == "needs_clarification":
        return MeetingActionExecution(
            "needs_clarification",
            "I need one more detail before I can do that from the meeting.",
            "meeting_action_needs_clarification",
        )
    if status == "needs_confirmation":
        return MeetingActionExecution(
            "needs_confirmation",
            "That needs owner confirmation before I can do it from the meeting.",
            "meeting_action_needs_confirmation",
        )
    return MeetingActionExecution(
        "failed",
        "I tried, but that meeting action could not be completed or verified.",
        "meeting_action_failed",
    )


def _status_from_tool_result(result: str) -> str:
    match = re.search(r"^Status:\s*([a-z_]+)\s*$", str(result or ""), flags=re.MULTILINE)
    return match.group(1) if match else "completed"
