from __future__ import annotations

import re

from maya_harness.harness_state import HarnessState


def classify_workflow(text: str) -> str:
    lowered = " ".join(text.lower().split())
    if any(marker in lowered for marker in ("self heal", "self-heal", "repair maya", "fix maya")):
        # Self-heal outranks generic keywords: "self heal the browser smoke"
        # is a repair request, not a browsing request.
        return "self_heal"
    if any(marker in lowered for marker in ("visual workflow", "workflow diagram", "architecture diagram", "mermaid visual", "flow diagram", "map this idea visually")):
        return "document"
    if any(word in lowered for word in ("document", "docx", "markdown", "presentation", "pptx", "excel", "xlsx", "spreadsheet", "sheet", "draw", "folder", "file")):
        return "document"
    if "project" in lowered or "readme" in lowered:
        return "project"
    if lowered.startswith(("open ", "switch to ", "press ", "type ")):
        return "app"
    if "open" in lowered and any(word in lowered for word in ("chrome", "browser", "safari")) and "flight" not in lowered:
        return "app"
    if any(word in lowered for word in ("flight", "browse", "browser", "google", "search online", "chrome")):
        return "browser"
    if any(word in lowered for word in ("screen", "slide", "powerpoint", "what about now", "diagram")):
        return "screen"
    if "skill" in lowered or re.search(r"\b(book me a hotel|shopping|calendar booking)\b", lowered):
        return "skill"
    if "self heal" in lowered or "repair maya" in lowered:
        return "self_heal"
    return "general"


def workflow_for_action(action_type: str) -> str:
    return {
        "create_skill_scaffold": "skill",
        "scheduled_briefing": "scheduled",
        "summarize_history": "scheduled",
        "digest_omi": "omi_distillation",
    }.get(action_type, "scheduled")


def plan_for(workflow_type: str) -> list[str]:
    plans = {
        "browser": ["open or inspect browser", "observe visible result", "stop before sensitive action"],
        "screen": ["capture fresh screen", "answer from visible context"],
        "document": ["create or update artifact", "record artifact", "open or attach result"],
        "project": ["resolve project", "update active project", "record project context"],
        "skill": ["draft skill proposal", "record scaffold", "wait for activation tests"],
        "self_heal": ["detect issue", "propose patch direction", "list tests", "wait for approval"],
        "scheduled": ["prepare message", "deliver through configured channel"],
    }
    return plans.get(workflow_type, ["choose tool", "execute safe action", "verify result"])


def next_step_for(state: HarnessState, keep_open: bool) -> str:
    if not keep_open:
        return "workflow complete"
    workflow = state.get("workflow_type", "general")
    if workflow == "browser":
        return "ask me to compare, change filters, click a safe result, or stop before booking"
    if workflow == "screen":
        return "ask a follow-up and I will capture the current screen"
    if workflow == "self_heal":
        return "review the repair proposal before any patch or restart"
    return "tell me the next step"
