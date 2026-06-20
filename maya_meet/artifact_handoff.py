from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class MeetArtifactHandoff:
    request: str
    tool_args: dict[str, object]
    artifact_type: str
    context_lines: tuple[str, ...]
    reason_code: str = "meet_artifact_context_scoped"


ARTIFACT_TYPE_ARGS = {
    "docx": "word_document",
    "xlsx": "excel_workbook",
    "pptx": "powerpoint_deck",
}


def build_meet_artifact_handoff(
    prompt: str,
    *,
    action_class: str,
    meeting_context_lines: list[str] | tuple[str, ...] | None,
    session_id: str = "",
    max_context_lines: int = 12,
) -> MeetArtifactHandoff | None:
    context = _scoped_context(meeting_context_lines, max_lines=max_context_lines)
    if not _context_sufficient(context):
        return None
    artifact_type = _artifact_type(prompt, action_class)
    label = _artifact_label(artifact_type)
    user_request = str(prompt or "").strip()
    scoped_request = _semantic_request(label)
    tool_args = {
        "request": scoped_request,
        "artifact_type": ARTIFACT_TYPE_ARGS[artifact_type],
        "artifact_topic": "current meeting transcript",
        "topic": "current meeting transcript",
        "audience": "meeting participants",
        "source": "meet_room",
        "meet_session_id": session_id,
        "meet_context_source": "current_meeting_transcript",
        "meet_context_lines": list(context),
        "meet_user_request": user_request,
        "meeting_context_policy": "current_transcript_only",
    }
    return MeetArtifactHandoff(scoped_request, tool_args, artifact_type, context)


def build_meet_revision_instruction(
    prompt: str,
    *,
    meeting_context_lines: list[str] | tuple[str, ...] | None,
    max_context_lines: int = 12,
) -> str | None:
    context = _scoped_context(meeting_context_lines, max_lines=max_context_lines)
    if not _context_sufficient(context):
        return None
    return (
        f"{str(prompt or '').strip()}\n\n"
        "Use only this current meeting transcript as supporting context for any meeting reference:\n"
        f"{_bullet_context(context)}"
    )


def _semantic_request(label: str) -> str:
    return f"Create a {label} from the current meeting transcript."


def _artifact_type(prompt: str, action_class: str) -> str:
    lowered = str(prompt or "").lower()
    if any(token in lowered for token in ("excel", "spreadsheet", "workbook", "xlsx")):
        return "xlsx"
    if any(token in lowered for token in ("powerpoint", "presentation", "slides", "deck", "pptx")):
        return "pptx"
    return "docx"


def _artifact_label(artifact_type: str) -> str:
    return {
        "xlsx": "Excel workbook",
        "pptx": "PowerPoint deck",
    }.get(artifact_type, "Word document")


def _scoped_context(
    meeting_context_lines: list[str] | tuple[str, ...] | None,
    *,
    max_lines: int,
) -> tuple[str, ...]:
    lines = []
    for line in meeting_context_lines or ():
        clean = " ".join(str(line or "").split()).strip()
        if clean:
            lines.append(clean[:500])
    return tuple(lines[-max(1, max_lines) :])


def _bullet_context(context: tuple[str, ...]) -> str:
    return "\n".join(f"- {line}" for line in context)


def _context_sufficient(context: tuple[str, ...]) -> bool:
    if not context:
        return False
    meaningful = _meaningful_words(context)
    if len(context) >= 3 and len(meaningful) >= 8:
        return True
    return len(" ".join(context)) >= 160 and len(meaningful) >= 10


def _meaningful_words(context: tuple[str, ...]) -> set[str]:
    filler = {
        "a", "an", "and", "are", "be", "because", "but", "for", "i", "it", "is",
        "me", "my", "of", "okay", "ok", "sure", "that", "the", "this", "to",
        "we", "yeah", "yes", "you",
    }
    words: set[str] = set()
    for line in context:
        for word in re.findall(r"[a-z0-9]{2,}", str(line).lower()):
            if word not in filler:
                words.add(word)
    return words
