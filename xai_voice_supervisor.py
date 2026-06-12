from __future__ import annotations

from dataclasses import dataclass

from browser_capability import route_browser_capability


@dataclass(frozen=True)
class SupervisedVoiceWork:
    request: str
    kind: str
    tool_name: str
    acknowledgement: str


def classify_supervised_voice_work(
    transcript: str,
    *,
    browser_tool_name: str,
    work_tool_name: str,
) -> SupervisedVoiceWork | None:
    cleaned = " ".join(transcript.strip().split())
    if not cleaned:
        return None
    lowered = cleaned.lower()
    if _looks_like_status_question(lowered):
        return None
    if _looks_like_browser_work(cleaned, lowered):
        kind = _browser_kind(lowered)
        return SupervisedVoiceWork(
            request=cleaned,
            kind=kind,
            tool_name=browser_tool_name,
            acknowledgement=_acknowledgement_for(kind),
        )
    kind = _non_browser_kind(lowered)
    if not kind:
        return None
    return SupervisedVoiceWork(
        request=cleaned,
        kind=kind,
        tool_name=work_tool_name,
        acknowledgement=_acknowledgement_for(kind),
    )


def _looks_like_browser_work(cleaned: str, lowered: str) -> bool:
    route = route_browser_capability(cleaned)
    if route.child_skill != "general_browser":
        return True
    command_markers = (
        "google ",
        "google search",
        "search for ",
        "search ",
        "look up ",
        "find online ",
        "check online ",
        "open chrome",
        "open browser",
        "open website",
        "go to ",
        "visit ",
    )
    return any(marker in lowered for marker in command_markers)


def _browser_kind(lowered: str) -> str:
    if "image" in lowered or "images" in lowered:
        return "browser_images"
    if "flight" in lowered or "flights" in lowered:
        return "browser_flights"
    if any(word in lowered for word in ("hotel", "booking.com", "airbnb", "accommodation", "accomodation")):
        return "browser_travel"
    if "youtube" in lowered or "video" in lowered:
        return "browser_youtube"
    if "reddit" in lowered:
        return "browser_reddit"
    return "browser"


def _non_browser_kind(lowered: str) -> str:
    if _looks_like_visual_work(lowered):
        return "visual_workflow"
    if _looks_like_artifact_work(lowered):
        return "document"
    if _looks_like_code_or_project_work(lowered):
        return "project_work"
    return ""


def _looks_like_visual_work(lowered: str) -> bool:
    markers = (
        "map this visually",
        "visual workflow",
        "workflow diagram",
        "architecture diagram",
        "mermaid",
        "flow diagram",
        "diagram for",
    )
    return any(marker in lowered for marker in markers)


def _looks_like_artifact_work(lowered: str) -> bool:
    if _looks_like_artifact_edit_work(lowered):
        return True
    action_prefixes = (
        "make ",
        "create ",
        "write ",
        "prepare ",
        "generate ",
        "build ",
        "draft ",
    )
    artifact_terms = (
        "document",
        "word",
        "docx",
        "excel",
        "spreadsheet",
        "sheet",
        "budget",
        "budgeting",
        "powerpoint",
        "presentation",
        "slide",
        "slides",
        "pptx",
        "markdown",
        "md file",
        "html",
        "file",
    )
    if lowered.startswith(action_prefixes) and any(term in lowered for term in artifact_terms):
        return True
    return any(
        phrase in lowered
        for phrase in (
            "make me a",
            "create me a",
            "write me a",
            "make an excel",
            "make a word",
            "make a powerpoint",
            "make a presentation",
            "make a budget",
            "create a budget",
            "write a document",
            "create a document",
        )
    )


def _looks_like_artifact_edit_work(lowered: str) -> bool:
    edit_starts = (
        "actually ",
        "make it ",
        "it's for ",
        "it’s for ",
        "it is for ",
        "for my ",
        "for our ",
        "for the ",
        "also include ",
        "include ",
        "add ",
        "change it ",
        "update it ",
        "use this context",
        "rewrite ",
    )
    artifact_or_content_terms = (
        "document",
        "word",
        "doc",
        "excel",
        "spreadsheet",
        "sheet",
        "powerpoint",
        "presentation",
        "slide",
        "summary",
        "executive",
        "section",
        "column",
        "formula",
        "notes",
        "audience",
        "ed",
    )
    if not lowered.startswith(edit_starts):
        return False
    return any(term in lowered for term in artifact_or_content_terms)


def _looks_like_code_or_project_work(lowered: str) -> bool:
    if any(
        phrase in lowered
        for phrase in (
            "fix the code",
            "update the code",
            "patch this",
            "implement this",
            "run the tests",
            "check the logs",
            "inspect the logs",
            "debug this",
        )
    ):
        return True
    return lowered.startswith(("fix ", "implement ", "debug ", "test ")) and any(
        word in lowered for word in ("maya", "kampung ai", "app", "code", "repo", "project")
    )


def _acknowledgement_for(kind: str) -> str:
    if kind == "browser_images":
        return "Okay, I’m searching the images now."
    if kind in {"browser_flights", "browser_travel"}:
        return "Okay, I’m checking that now."
    if kind in {"browser", "browser_youtube", "browser_reddit"}:
        return "Okay, I’m opening that now."
    if kind == "visual_workflow":
        return "Okay, I’m mapping that now."
    if kind == "project_work":
        return "Okay, I’m checking that now."
    return "Okay, I’m making that now."


def _looks_like_status_question(lowered: str) -> bool:
    status_markers = (
        "what are you doing",
        "what are you working on",
        "what did you do",
        "what happened",
        "show the request",
        "pull up the request",
        "status",
        "is it ready",
        "are you done",
        "how will you search",
        "who will be doing",
    )
    return any(marker in lowered for marker in status_markers)
