from __future__ import annotations

import re
from pathlib import Path

from maya_voice.verified_facts import facts_block, work_fact

OFFICE_SUFFIXES = {".docx", ".xlsx", ".pptx"}
VOICE_PATH_SUFFIXES = ("docx", "xlsx", "pptx", "md", "html", "png", "svg", "pdf")


def tool_result_for_maya(request: str, result: str, *, status: str = "completed") -> str:
    voice_result = voice_safe_paths(result)
    instructions = {
        "failed": (
            "The action failed or could not be verified. Tell Zainal that directly. Do not say the browser opened "
            "or that he should see the page unless the result says it opened and was verified."
        ),
        "needs_clarification": (
            "The result is a reason code, not wording to read aloud. Ask a natural clarification in Maya's own words. "
            "Do not say the work started. When Zainal answers, call the same tool again with the original request "
            "and his clarification combined. Do not mention internal architecture details."
        ),
        "needs_confirmation": (
            "The result is a confirmation request, not wording to read aloud. Ask Zainal naturally whether to proceed "
            "with the specific named action or artifact. Do not say the work started or completed."
        ),
    }
    instruction = instructions.get(status) or (
        "Use this result to answer Zainal as Maya. Do not mention internal architecture details. For files, say the "
        "friendly file name and the Maya folder, not a slash path or file extension, unless Zainal explicitly asks "
        "for the exact path. If the result says the file was opened or was asked to open, do not offer to open it again."
    )
    return f"Request: {request}\nStatus: {status}\n{instruction}\nResult:\n{voice_result}"


def failed_tool_result_for_maya(request: str, reason: object, *, work_id: str | None = None) -> str:
    facts = facts_block([work_fact(work_active=False, phase="failed", work_id=work_id)])
    return tool_result_for_maya(
        request,
        f"I could not finish that request. Reason: {reason}\n{facts}",
        status="failed",
    )


def structured_work_request(args: dict, question: str = "") -> str:
    request = str(args.get("request") or question or "").strip()
    artifact_type = str(args.get("artifact_type") or "auto").strip().lower()
    topic = str(args.get("artifact_topic") or "").strip()
    content = topic or request
    if artifact_type in {"", "auto"}:
        return request
    prefix = {
        "word_document": "Create a Word document about",
        "excel_workbook": "Create an Excel workbook about",
        "powerpoint_deck": "Create a PowerPoint deck about",
        "markdown_note": "Create a Markdown note about",
        "html_file": "Create an HTML file about",
    }.get(artifact_type)
    if not prefix or not content:
        return request
    lowered = request.lower()
    if artifact_type == "word_document" and any(marker in lowered for marker in ("word document", "word doc", "docx")):
        return request
    if artifact_type == "excel_workbook" and any(marker in lowered for marker in ("excel", "workbook", "spreadsheet", "xlsx")):
        return request
    if artifact_type == "powerpoint_deck" and any(marker in lowered for marker in ("powerpoint", "presentation", "slides", "deck", "pptx")):
        return request
    if artifact_type == "markdown_note" and any(marker in lowered for marker in ("markdown", "md file", "md note")):
        return request
    if artifact_type == "html_file" and "html" in lowered:
        return request
    return f"{prefix} {content}"


def sanitize_internal_language(text: str) -> str:
    replacements = {
        "Browser skill ": "",
        "Google Search skill ": "Google Search ",
        "Google Images skill ": "Google Images ",
        "YouTube Research skill ": "YouTube ",
        "Reddit Research skill ": "Reddit ",
        "Google Cloud Console skill ": "Google Cloud Console ",
        "Maya's work lane": "Maya",
        "normal work lane": "Maya",
        "worker lane": "Maya",
        "handoff": "work request",
        "Handoff": "Work request",
        "paid voice session": "voice session",
        "Gemini": "Maya",
        "Claude": "Maya",
        "Artisan": "Maya",
    }
    cleaned = text
    for source, target in replacements.items():
        cleaned = cleaned.replace(source, target)
    return cleaned.strip()


def voice_display_name_from_path(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if ":" in raw and raw.startswith(("Macintosh HD:", "Users:", "/:Users:")):
        name = raw.split(":")[-1]
    else:
        name = Path(raw).name
    if not name:
        return ""
    suffix = Path(name).suffix.lower()
    return Path(name).stem if suffix in OFFICE_SUFFIXES else name


def browser_result_failed(text: str) -> bool:
    lowered = " ".join(text.lower().split())
    failure_markers = (
        "i could not inspect chrome yet",
        "i could not finish the browser action",
        "i could not open",
        "could not open that result",
        "could not find a visible result",
        "could not verify",
        "cannot confirm",
        "no maya tab open yet",
        "extension op",
        "cannot access contents of url",
        "has no results page open",
        "tell me what to search first",
        "what should i search for",
        "what image topic should i search for",
        "which visible browser item should i click",
        "tell me the field and value to fill",
        "browser_bridge_unavailable",
        "browser_group_verification_failed",
    )
    return any(marker in lowered for marker in failure_markers)


def local_work_result_needs_clarification(assistant, text: str) -> bool:
    try:
        if getattr(getattr(assistant, "commands", None), "last_lane", "") == "clarification":
            return True
        documents = getattr(getattr(assistant, "commands", None), "documents", None)
        if getattr(documents, "last_model_lane", "") == "clarification":
            return True
    except Exception:
        pass
    lowered = " ".join(str(text or "").lower().split())
    clarification_markers = (
        "which type should i create",
        "word doc, excel sheet, or powerpoint",
        "how many days should",
        "which city or destination",
        "what system, product, or workflow",
        "what is the proposal for",
        "what topic should",
        "what should the budget tracker be for",
    )
    return lowered.endswith("?") and any(marker in lowered for marker in clarification_markers)


def voice_safe_paths(text: str) -> str:
    def display_name(path: Path) -> str:
        return path.stem if path.suffix.lower() in OFFICE_SUFFIXES else path.name

    def folder_display(parts: tuple[str, ...], name: str) -> str:
        if "Maya" in parts:
            index = parts.index("Maya")
            if index + 1 < len(parts):
                return f"the Maya {parts[index + 1]} folder ({name})"
        return name

    def replace_posix(match: re.Match[str]) -> str:
        raw = match.group(1).strip(" .)")
        path = Path(raw)
        return folder_display(path.parts, display_name(path))

    def replace_hfs(match: re.Match[str]) -> str:
        raw = match.group(1).strip(" .)")
        parts = tuple(part for part in raw.split(":") if part)
        name = parts[-1] if parts else raw
        display = Path(name).stem if Path(name).suffix.lower() in OFFICE_SUFFIXES else name
        return folder_display(parts, display)

    def replace_office_name(match: re.Match[str]) -> str:
        return Path(match.group(1)).stem

    safe = re.sub(rf"(/Users/[^\n\r\t]+?\.(?:{'|'.join(VOICE_PATH_SUFFIXES)}))", replace_posix, text)
    safe = re.sub(rf"((?:Macintosh HD|/):Users:[^\n\r\t]+?\.(?:{'|'.join(VOICE_PATH_SUFFIXES)}))", replace_hfs, safe)
    safe = re.sub(r"\b([A-Za-z0-9][A-Za-z0-9_. -]{0,120}\.(?:docx|xlsx|pptx))\b", replace_office_name, safe)
    return safe
