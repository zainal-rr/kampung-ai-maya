from __future__ import annotations

import re

START_COMMAND_RE = re.compile(
    r"^(?:please\s+|maya[,\s]+)?"
    r"(?:open|switch\s+to|press|type|draw|browse|google)\b",
    re.IGNORECASE,
)
START_MARKERS = (
    "check flight", "find flight", "find flights", "search flight", "search flights",
    "book flight", "search online", "make presentation", "create presentation",
    "write a word", "create a docx", "make an excel", "create an excel",
    "write an excel", "make a spreadsheet", "create a spreadsheet", "make an xlsx",
    "create an xlsx", "create an md", "make a markdown", "create drawing",
    "open project", "switch project", "self heal", "repair maya", "book me a hotel",
    "look at my screen",
)
FOLLOWUP_MARKERS = (
    "continue", "what about now", "how about now", "change the date", "find cheaper",
    "make it cheaper", "open it", "show me", "save it", "use this project", "click ", "fill ",
)
STOP_MARKERS = {"stop workflow", "close workflow", "end workflow", "cancel workflow"}
RESUME_MARKERS = {"what are you working on", "where did we stop", "what is pending", "workflow status"}
ARTIFACT_MARKERS = {"what files did you create", "show me the latest artifact", "which screenshot did you use"}
COMMAND_BYPASS_MARKERS = {
    "open the last document", "open latest document", "what was the last document you created",
    "what is the last document you created", "what was the latest document you created",
    "what is the latest document you created", "what document did you just create",
    "what document did you create just now", "what file did you just create",
    "what file did you create just now", "what did you just create",
    "what did you create just now", "what document did you create", "what file did you create",
    "what was the last document", "what is the last document", "last document", "latest document",
}
FILE_OPEN_BYPASS_RE = re.compile(
    r"^(?:open|show(?: me)?)\s+(?:latest\s+|the\s+latest\s+)?"
    r"(?:word|docx|document|powerpoint|presentation|pptx|excel|spreadsheet|xlsx|markdown|md)\b",
    re.I,
)


def is_start(lowered: str, markers: tuple[str, ...]) -> bool:
    return bool(START_COMMAND_RE.match(lowered)) or any(marker in lowered for marker in markers)


def is_followup(lowered: str, markers: tuple[str, ...]) -> bool:
    if lowered.startswith(("compare ", "explain ", "what is ", "what are ")):
        return False
    return any(marker in lowered for marker in markers)


def thread_id(run_id: str) -> str:
    return f"harness:{run_id}"


def continuing_prefix(active: dict) -> str:
    workflow = str(active.get("workflow_type") or "workflow")
    goal = str(active.get("goal") or "").strip()
    return f"Continuing: {workflow}" + (f" for {goal}." if goal else ".")
