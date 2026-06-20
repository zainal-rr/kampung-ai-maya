from __future__ import annotations

from maya_documents.document_actions_context import *
from maya_documents.artifact_file_state import record_artifact_fingerprint
from maya_documents.document_actions_excel_rows import _budget_rows, _saas_tracker_rows, _task_tracker_rows, _travel_budget_topic


def _quick_request(topic: str) -> bool:
    low = topic.lower()
    return any(word in low for word in ("quick", "rough", "starter", "simple", "just draft"))


def _should_defer_html_app_to_artisan(text: str) -> bool:
    lowered = " ".join(str(text).lower().split())
    if any(marker in lowered for marker in ("html file", "single html", "one html", "self contained html", "self-contained html")):
        return False
    return any(marker in lowered for marker in (" app", "web app", "planner", "tracker", "dashboard", "ui"))


def _draft_delivery_request(text: str) -> bool:
    lowered = " ".join(str(text).lower().split())
    if "draft" not in lowered:
        return False
    return any(
        marker in lowered
        for marker in (
            "give me the draft",
            "give me draft",
            "just give me the draft",
            "open the draft",
            "show me the draft",
            "send me the draft",
        )
    )


async def _remember_draft_artifact(db_path: str, path: Path, channel: str, label: str, topic: str = "") -> None:
    artifact_type = path.suffix.lower().lstrip(".")
    draft_topic = topic or re.sub(r"[-_]+", " ", path.stem).strip() or label
    await upsert_preference(db_path, LAST_DOC_KEY, str(path), source="document")
    await upsert_preference(db_path, LAST_DRAFT_DOC_KEY, str(path), source="document")
    await record_artifact_fingerprint(db_path, path)
    await record_artifact_session(db_path, channel, artifact_type, path, draft_topic)


def _strip_quality_words(topic: str) -> str:
    return re.sub(r"\b(quick|rough|starter|simple|just draft)\b", " ", topic, flags=re.I).strip(" .") or topic


def _retired_kampung_ai_cost_topic(topic: str) -> bool:
    low = topic.lower()
    if _saas_tracker_topic(topic):
        return False
    cost_markers = (
        "cost",
        "budget",
        "spend",
        "usage",
        "token",
        "tokens",
        "provider calls",
        "voice seconds",
        "api cost",
        "model cost",
        "cost tracker",
        "usage tracker",
    )
    return "kampung ai" in low and any(marker in low for marker in cost_markers)


def _saas_tracker_topic(topic: str) -> bool:
    low = topic.lower()
    return any(marker in low for marker in ("saas", "subscription", "renewal", "plan")) and any(
        marker in low for marker in ("cost", "budget", "tracker", "spend")
    )


def _excel_lane(topic: str) -> str:
    if _saas_tracker_topic(topic):
        return "Local SaaS cost tracker workbook"
    if is_kampung_ai_testing_comparison(topic):
        return "Local Kampung AI testing comparison"
    return "Gemini Flash role-based spreadsheet draft"


def _internal_excel_topic(topic: str) -> bool:
    return _saas_tracker_topic(topic) or is_kampung_ai_testing_comparison(topic)


def _prefixed_lane(lane: str, preflight: ArtifactPreflight | None) -> str:
    return f"{preflight.lane_prefix} + {lane}" if preflight else lane


def _budget_topic(topic: str) -> bool:
    from maya_documents.excel_species import detect_excel_species

    if detect_excel_species(topic):
        # A domain species (content calendar, inventory, research log, ...)
        # should not be flattened into the generic budget skeleton just
        # because the topic says "tracker".
        return False
    low = topic.lower()
    budget_markers = ("budget", "budgeting", "expense", "cost", "spend", "spending", "tracker", "trip")
    food_markers = ("food", "restaurant", "restaurants", "meal", "meals", "mill", "mills", "mail", "mails", "dining", "cafe", "cafes")
    return any(word in low for word in budget_markers) or any(word in low for word in food_markers)


def _task_tracker_topic(topic: str) -> bool:
    from maya_documents.excel_species import detect_excel_species

    if detect_excel_species(topic):
        # Domain trackers (YouTube, farm, research, ...) get their own schema
        # instead of the shared office Task/Owner/Priority skeleton.
        return False
    lowered = topic.lower()
    if any(word in lowered for word in ("budget", "expense", "cost", "variance", "spend")):
        return False
    tracker_marker = any(word in lowered for word in ("task tracker", "work tracker", "status tracker", "tracking sheet", "tracker"))
    office_marker = any(word in lowered for word in ("office", "work", "team", "project", "owner", "due date", "status", "priority"))
    return tracker_marker and office_marker


def _budget_filename_topic(topic: str) -> str:
    lowered = topic.lower()
    destination = _destination_from_topic(lowered)
    if destination:
        return f"{destination} budget tracker"
    return re.sub(r"\b(?:budget|budgeting|tracker|spreadsheet|sheet|excel|xlsx)\b", " ", topic, flags=re.I).strip() or "budget tracker"


def _budget_title(topic: str) -> str:
    destination = _destination_from_topic(topic.lower())
    return f"{destination.title()} Budget Tracker" if destination else "Budget Tracker"


def _destination_from_topic(lowered: str) -> str:
    match = re.search(r"\b(?:for|about|to|in)\s+([a-z][a-z\s]{1,40}?)(?:\s+from|\s+for\s+\d|\s+on\s+|\s+between\s+|$)", lowered)
    if not match:
        return ""
    candidate = re.sub(r"\b(?:a|an|the|trip|budget|tracker|spreadsheet|sheet|excel|xlsx)\b", " ", match.group(1))
    return " ".join(candidate.split())


def _append_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)


def _html_content(raw: str, topic: str) -> str:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("html"):
            cleaned = cleaned[4:].strip()
    if "<html" in cleaned.lower() and "<!doctype" in cleaned.lower():
        return cleaned.rstrip() + "\n"
    title = topic.strip().title() or "Maya HTML App"
    escaped = _escape_html(cleaned)
    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"UTF-8\">\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
        f"  <title>{_escape_html(title)}</title>\n"
        "  <style>\n"
        "    body { font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.5; }\n"
        "    main { max-width: 760px; margin: auto; }\n"
        "    pre { white-space: pre-wrap; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "  <main>\n"
        f"    <h1>{_escape_html(title)}</h1>\n"
        f"    <pre>{escaped}</pre>\n"
        "  </main>\n"
        "</body>\n"
        "</html>\n"
    )


def _looks_like_html_app(content: str) -> bool:
    lowered = content.lower()
    if not all(marker in lowered for marker in ("<!doctype", "<html", "<style", "<script")):
        return False
    if "<pre>" in lowered and ("### " in content or "# " in content):
        return False
    interactive_markers = ("<button", "<input", "<select", "<textarea", "addeventlistener", "localstorage")
    return any(marker in lowered for marker in interactive_markers)


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _attach(message: str, path: Path, channel: str) -> str:
    return f"{message}\n[file:{path}]" if channel == "telegram" else message


def _artifact_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return "spreadsheet"
    if suffix == ".pptx":
        return "presentation"
    if suffix == ".docx":
        return "document"
    if suffix == ".md":
        return "note"
    return "file"
