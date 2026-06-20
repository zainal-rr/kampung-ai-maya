from __future__ import annotations

from maya_documents.artifact_preflight import ArtifactPreflight
from maya_voice.artifact_manifest import get_manifest
from maya_voice.work_runtime import current_voice_work_db_path, current_voice_work_id


MEET_CONTEXT_SOURCE = "current_meeting_transcript"


async def append_current_meet_context_to_preflight(preflight: ArtifactPreflight) -> ArtifactPreflight:
    extra = await current_meet_artifact_extra_context()
    if not extra:
        return preflight
    content = f"{preflight.content}\n\n{extra}".strip()
    return ArtifactPreflight(
        preflight.artifact_type,
        preflight.topic,
        preflight.source,
        content,
        preflight.cost_recorded,
        preflight.doc_kind,
    )


async def current_meet_artifact_extra_context() -> str:
    db_path = current_voice_work_db_path()
    work_id = current_voice_work_id()
    if not db_path or not work_id:
        return ""
    manifest = await get_manifest(db_path, work_id)
    return meet_artifact_extra_context_from_manifest(manifest or {})


def meet_artifact_extra_context_from_manifest(manifest: dict) -> str:
    intent = dict((manifest or {}).get("structured_intent") or {})
    if not _is_meet_intent(intent):
        return ""
    lines = _clean_lines(intent.get("meet_context_lines"))
    if not lines:
        return ""
    request = " ".join(str(intent.get("meet_user_request") or "").split())
    parts = [
        "Meet artifact source contract:",
        "- Use only the current meeting transcript below as factual meeting context for this artifact.",
        "- Do not use prior artifacts, browser pages, memory, trip plans, travel plans, or old context.",
        "- Derive the title, sections, sheets, or slides semantically from this transcript.",
        "- For Word, start the Markdown with one content-specific # title derived from the transcript, not a generic meeting heading.",
        "- If this transcript is too thin for the request, say more meeting context is needed instead of inventing.",
    ]
    if request:
        parts.append(f"Addressed meeting request: {request}")
    parts.append("Source meeting transcript:")
    parts.extend(f"- {line}" for line in lines)
    return "\n".join(parts)


async def current_meet_artifact_title_from_markdown(markdown: str, fallback: str = "") -> str:
    db_path = current_voice_work_db_path()
    work_id = current_voice_work_id()
    manifest = await get_manifest(db_path, work_id) if db_path and work_id else None
    return meet_artifact_title_from_manifest(markdown, manifest or {}, fallback=fallback)


def meet_artifact_title_from_manifest(markdown: str, manifest: dict, *, fallback: str = "") -> str:
    intent = dict((manifest or {}).get("structured_intent") or {})
    manifest_title = " ".join(str((manifest or {}).get("title") or "").split()).strip()
    if not _is_meet_intent(intent):
        return manifest_title or fallback or "Maya Word Document"
    if manifest_title and not _generic_meet_title(manifest_title):
        return manifest_title
    markdown_title = _markdown_title(markdown)
    if markdown_title and not _generic_meet_title(markdown_title) and not _generic_section_title(markdown_title):
        return markdown_title
    derived = _derive_title_from_context(_clean_lines(intent.get("meet_context_lines")))
    return derived or fallback or "Meeting Notes"


def _clean_lines(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    lines: list[str] = []
    for item in value:
        clean = " ".join(str(item or "").split()).strip()
        if clean:
            lines.append(clean[:500])
    return lines[-12:]


def _is_meet_intent(intent: dict) -> bool:
    return (
        str(intent.get("source") or "") == "meet_room"
        and str(intent.get("meet_context_source") or "") == MEET_CONTEXT_SOURCE
    )


def _markdown_title(markdown: str) -> str:
    for raw in str(markdown or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            return line.lstrip("#").strip(" :-")
        return ""
    return ""


def _generic_meet_title(title: str) -> bool:
    normalized = _normalize_title(title)
    return normalized in {
        "current meeting transcript",
        "current meeting",
        "meeting transcript",
        "from document",
        "from current",
        "maya word document",
    }


def _generic_section_title(title: str) -> bool:
    normalized = _normalize_title(title)
    return normalized in {
        "meeting summary",
        "summary",
        "overview",
        "key points",
        "decisions",
        "action items",
        "open questions",
        "follow up",
        "next steps",
    }


def _derive_title_from_context(lines: list[str]) -> str:
    if not lines:
        return ""
    for line in lines:
        title = _capitalized_phrase_title(line)
        if title:
            return title
    first = lines[0].split(".", 1)[0].strip()
    first = " ".join(first.split()[:6]).strip(" :-")
    return _title_case(first) if first else ""


def _capitalized_phrase_title(line: str) -> str:
    import re

    for match in re.finditer(r"\b[A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*){0,4}\b", line):
        phrase = match.group(0).strip()
        if _normalize_title(phrase) not in {"i", "we", "the", "this", "that", "maya"}:
            return phrase
    return ""


def _title_case(text: str) -> str:
    replacements = {"ai": "AI", "api": "API", "imac": "iMac"}
    words = []
    for word in text.split():
        clean = word.strip()
        words.append(replacements.get(clean.lower(), clean.capitalize()))
    return " ".join(words)


def _normalize_title(title: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", " ", str(title or "").lower()).strip()
