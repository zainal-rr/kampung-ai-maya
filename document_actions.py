from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

from artifact_naming import named_artifact_path
from artifact_quality import (
    extract_docx_text,
    extract_xlsx_text,
    review_artifact_quality,
    validate_docx_path,
    validate_html_content,
    validate_xlsx_path,
)
from cost_spreadsheet import kampung_ai_cost_rows
from created_file_opener import open_created_file
from document_failures import document_generation_failed
from document_request_parser import document_request, markdown_update
from document_style import style_document_text, style_sections, style_table
from html_reviewer import review_html_app
from office_drafter import sections_from_markdown, slides_from_markdown, spreadsheet_from_markdown
from office_modern_files import create_docx, create_xlsx
from pptx_document_flow import create_powerpoint_with_qa
from presentation_reviewer import review_presentation_slides
from harness_artifact_store import record_structured_artifact
from harness_models import local_artifact
from markdown_drafter import MarkdownDraft, draft_html_with_gemini, draft_html_with_kimi, draft_markdown_with_gemini, html_builder_lane, should_use_model_draft
from permission_policy import action_permission, contains_sensitive_info, hard_no_private_exposure_text, path_allowed
from project_store import active_project, remember_project_note
from storage import get_preference, upsert_preference
from testing_spreadsheet import is_kampung_ai_testing_comparison, kampung_ai_testing_rows
from utils import OSBridge
from visual_workflow import VisualWorkflowRenderer
from workspace_paths import workspace_dir


logger = logging.getLogger(__name__)
LAST_DOC_KEY = "maya_last_document_path"
DIRECT_DOC_RUN_ID = "direct_document_actions"


class DocumentActionRouter:
    def __init__(self, db_path: str, workspace: Path | None = None, bridge: OSBridge | None = None):
        self.db_path = db_path
        self.workspace = workspace or workspace_dir("")
        self.bridge = bridge or OSBridge()
        self.visual_workflow = VisualWorkflowRenderer(db_path, self.bridge)
        self.last_model_lane = ""
        self.last_cost_recorded = False

    async def handle(self, text: str, channel: str) -> str | None:
        visual = await self.visual_workflow.handle(text, channel)
        if visual:
            self.last_model_lane = "Local visual workflow renderer"
            self.last_cost_recorded = False
            return visual
        update = markdown_update(text)
        if update:
            return await self._update_markdown(update, channel)
        request = document_request(text)
        if request is None:
            return None
        kind, topic, project_scoped = request
        if project_scoped and not await active_project(self.db_path):
            return "No active project yet. Open or create a project first, then I can put it under that project's docs folder."
        if contains_sensitive_info(topic):
            return hard_no_private_exposure_text()
        if action_permission("create_document" if kind != "pptx" else "create_presentation") != "allow":
            return "I need your confirmation before creating that document."
        if kind == "md":
            return await self._create_markdown(topic, project_scoped, channel)
        if kind == "html":
            return await self._create_html(topic, project_scoped, channel)
        if kind == "docx":
            return await self._create_word(topic, project_scoped, channel)
        if kind == "xlsx":
            return await self._create_excel(topic, project_scoped, channel)
        return await self._create_powerpoint(topic, channel)

    async def _create_markdown(self, topic: str, project_scoped: bool, channel: str) -> str:
        self.last_model_lane = ""
        self.last_cost_recorded = False
        path = await self._path("md", topic, project_scoped)
        try:
            content = await self._markdown_content(topic)
            content = await style_document_text(self.db_path, content)
        except Exception as exc:
            return document_generation_failed("Markdown file", exc)
        if not path_allowed(path):
            return f"I can't write to {path}."
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_text, content, "utf-8")
        await self._remember(path, "Created Markdown draft", project_scoped)
        return await self._done("Markdown draft", path, channel, app_name=None)

    async def _create_html(self, topic: str, project_scoped: bool, channel: str) -> str:
        self.last_model_lane = html_builder_lane()
        self.last_cost_recorded = False
        path = await self._path("html", topic, project_scoped)
        draft, lane = await self._html_draft(topic)
        if not draft:
            return document_generation_failed("HTML file", RuntimeError("Kimi and Gemini returned no usable HTML app."))
        self.last_model_lane = lane
        self.last_cost_recorded = True
        content = _html_content(draft.content, topic)
        if not _looks_like_html_app(content):
            fallback = await self._html_fallback(topic)
            if not fallback:
                return document_generation_failed("HTML file", RuntimeError("Kimi and Gemini returned a document instead of an app."))
            content, self.last_model_lane = fallback
        reviewed_content, review_status = await review_html_app(self.db_path, topic, content)
        if review_status == "reviewed" and _looks_like_html_app(reviewed_content):
            content = reviewed_content
            self.last_model_lane += " + Claude HTML review"
        elif review_status in {"reviewed", "rejected"}:
            self.last_model_lane += " + Claude HTML review rejected"
        elif review_status == "failed":
            self.last_model_lane += " + Claude HTML review failed"
        html_qa = validate_html_content(topic, content)
        self.last_model_lane += " + local HTML QA"
        if not path_allowed(path):
            return f"I can't write to {path}."
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_text, content, "utf-8")
        await self._remember(path, f"Created HTML app: {html_qa.summary}", project_scoped)
        if not html_qa.passed:
            return await self._draft_with_issues("HTML draft", path, channel, None, html_qa.short_issue_text())
        return await self._done("HTML file", path, channel, app_name=None)

    async def _html_draft(self, topic: str) -> tuple[MarkdownDraft | None, str]:
        kimi_failure = ""
        primary_lane = html_builder_lane()
        try:
            draft = await draft_html_with_kimi(self.db_path, topic)
        except TimeoutError as exc:
            logger.warning("%s failed for %r: %s: %s", primary_lane, topic, type(exc).__name__, exc)
            draft = None
            kimi_failure = f"{primary_lane.replace(' app builder', '')} timeout -> "
        except Exception as exc:
            logger.warning("%s failed for %r: %s: %s", primary_lane, topic, type(exc).__name__, exc)
            draft = None
            kimi_failure = f"{primary_lane.replace(' app builder', '')} failed -> "
        if draft:
            return draft, primary_lane
        logger.info("Using Gemini HTML fallback for %r", topic)
        fallback = await self._html_fallback(topic)
        if not fallback:
            return None, primary_lane
        content, lane = fallback
        return MarkdownDraft(content), f"{kimi_failure}{lane}" if kimi_failure else lane

    async def _html_fallback(self, topic: str) -> tuple[str, str] | None:
        try:
            draft = await draft_html_with_gemini(self.db_path, topic)
        except Exception as exc:
            logger.warning("Gemini HTML fallback failed for %r: %s", topic, exc)
            return None
        if not draft:
            return None
        content = _html_content(draft.content, topic)
        if not _looks_like_html_app(content):
            return None
        return content, "Gemini Flash HTML fallback"

    async def _markdown_content(self, topic: str) -> str:
        if should_use_model_draft(topic):
            self.last_model_lane = "Gemini Flash role-based document draft"
            self.last_cost_recorded = False
            draft = await draft_markdown_with_gemini(self.db_path, topic)
            if draft:
                self.last_model_lane = "Gemini Flash grounded role-based document draft" if draft.grounded else "Gemini Flash role-based document draft"
                self.last_cost_recorded = True
                return draft.content
            raise RuntimeError("Gemini returned no document content.")
        raise RuntimeError("Document generation requires Gemini Flash.")

    async def _create_word(self, topic: str, project_scoped: bool, channel: str) -> str:
        self.last_model_lane = "Gemini Flash role-based Word draft"
        self.last_cost_recorded = False
        path = await self._path("docx", topic, project_scoped)
        if not path_allowed(path):
            return f"I can't write to {path}."
        try:
            draft = await draft_markdown_with_gemini(self.db_path, topic)
        except Exception as exc:
            return document_generation_failed("Word document", exc)
        if not draft:
            return document_generation_failed("Word document", RuntimeError("Gemini returned no document content."))
        self.last_model_lane = "Gemini Flash grounded role-based Word draft" if draft.grounded else "Gemini Flash role-based Word draft"
        self.last_cost_recorded = True
        sections = await style_sections(self.db_path, sections_from_markdown(draft.content, topic))
        await asyncio.to_thread(create_docx, path, topic.title(), sections)
        local_qa = await asyncio.to_thread(validate_docx_path, path)
        self.last_model_lane += " + local Word QA"
        review_qa = await review_artifact_quality(self.db_path, "docx", topic, await asyncio.to_thread(extract_docx_text, path))
        if review_qa.review_model:
            self.last_model_lane += " + Claude Word review"
        elif review_qa.warnings:
            self.last_model_lane += " + Claude Word review skipped"
        quality = local_qa.merge(review_qa)
        await self._remember(path, f"Created Word draft: {quality.summary}", project_scoped)
        if not quality.passed:
            return await self._draft_with_issues("Word draft", path, channel, "Microsoft Word", quality.short_issue_text())
        return await self._done("Word draft", path, channel, "Microsoft Word")

    async def _create_powerpoint(self, topic: str, channel: str) -> str:
        quick = _quick_request(topic)
        topic = _strip_quality_words(topic)
        self.last_model_lane = "Gemini Flash role-based presentation content"
        self.last_cost_recorded = False
        path = named_artifact_path(self.workspace / "presentations", topic, "pptx")
        if not path_allowed(path):
            return f"I can't write to {path}."
        try:
            draft = await draft_markdown_with_gemini(self.db_path, topic)
        except Exception as exc:
            return document_generation_failed("PowerPoint", exc)
        if not draft:
            return document_generation_failed("PowerPoint", RuntimeError("Gemini returned no presentation content."))
        self.last_model_lane = (
            "Gemini Flash grounded role-based presentation content"
            if draft.grounded else "Gemini Flash role-based presentation content"
        )
        self.last_cost_recorded = True
        slides = await style_sections(self.db_path, slides_from_markdown(draft.content, topic))
        reviewed = await review_presentation_slides(self.db_path, topic, slides)
        if reviewed != slides:
            self.last_model_lane += " + Claude presentation design review"
            slides = reviewed
        slides = await style_sections(self.db_path, slides)
        qa = await create_powerpoint_with_qa(
            self.db_path,
            path,
            topic.title(),
            slides,
            DIRECT_DOC_RUN_ID,
            LAST_DOC_KEY,
            auto_improve=not quick,
        )
        if qa.revisions:
            self.last_model_lane += " + topic-safe polish pass"
        if not qa.passed:
            return _attach(
                f"I created a PowerPoint draft, but {qa.summary()} I’m not calling it final.",
                path,
                channel,
            )
        label = "starter PowerPoint draft" if quick else "PowerPoint draft"
        return await self._done(f"{label}. {qa.summary()}", path, channel, "Microsoft PowerPoint")

    async def _create_excel(self, topic: str, project_scoped: bool, channel: str) -> str:
        self.last_model_lane = _excel_lane(topic)
        self.last_cost_recorded = False
        path = await self._path("xlsx", topic, project_scoped)
        if not path_allowed(path):
            return f"I can't write to {path}."
        if _kampung_ai_cost_topic(topic):
            headers, rows = await kampung_ai_cost_rows(self.db_path)
            headers, rows = await style_table(self.db_path, headers, rows)
            await asyncio.to_thread(create_xlsx, path, "Kampung AI Cost Tracker", headers, rows)
            return await self._finish_excel(path, "Kampung AI cost tracker", topic, project_scoped, channel)
        if is_kampung_ai_testing_comparison(topic):
            headers, rows = kampung_ai_testing_rows()
            headers, rows = await style_table(self.db_path, headers, rows)
            await asyncio.to_thread(create_xlsx, path, "Kampung AI Testing Comparison", headers, rows)
            return await self._finish_excel(path, "Excel testing comparison", topic, project_scoped, channel)
        if _budget_topic(topic):
            if _travel_budget_topic(topic):
                from travel_budget import create_travel_budget_excel

                self.last_model_lane = "Gemini Flash role-based travel budget notes + Local travel budget workbook"
                self.last_cost_recorded = True
                return await create_travel_budget_excel(self.db_path, topic, self.bridge, channel)
            self.last_model_lane = "Local editable budget workbook"
            self.last_cost_recorded = False
            path = await self._path("xlsx", _budget_filename_topic(topic), project_scoped)
            headers, rows = _budget_rows(topic)
            headers, rows = await style_table(self.db_path, headers, rows)
            await asyncio.to_thread(create_xlsx, path, _budget_title(topic), headers, rows)
            return await self._finish_excel(path, "Excel budget tracker", topic, project_scoped, channel)
        try:
            draft = await draft_markdown_with_gemini(self.db_path, topic)
        except Exception as exc:
            return document_generation_failed("Excel spreadsheet", exc)
        if not draft:
            return document_generation_failed("Excel spreadsheet", RuntimeError("Gemini returned no spreadsheet content."))
        self.last_model_lane = "Gemini Flash grounded role-based spreadsheet draft" if draft.grounded else "Gemini Flash role-based spreadsheet draft"
        self.last_cost_recorded = True
        headers, rows = spreadsheet_from_markdown(topic, draft.content)
        headers, rows = await style_table(self.db_path, headers, rows)
        await asyncio.to_thread(create_xlsx, path, topic.title(), headers, rows)
        return await self._finish_excel(path, "Excel draft", topic, project_scoped, channel)

    async def _update_markdown(self, note: str, channel: str) -> str:
        path = await self._markdown_target()
        if path is None:
            return "Tell me which Markdown file to update first."
        if contains_sensitive_info(note):
            return hard_no_private_exposure_text()
        if path.suffix.lower() != ".md":
            return "The last document is not a Markdown file, so I will not edit it this way."
        note = await style_document_text(self.db_path, note.strip())
        addition = f"\n\n## Update\n\n{note}\n"
        await asyncio.to_thread(_append_text, path, addition)
        await upsert_preference(self.db_path, LAST_DOC_KEY, str(path), source="document")
        return _attach(f"Done. I updated the Markdown file at {path}.", path, channel)

    async def _path(self, kind: str, topic: str, project_scoped: bool) -> Path:
        project = await active_project(self.db_path) if project_scoped else None
        if project:
            return named_artifact_path(project.path / "docs", topic, kind)
        folder = {"md": "notes", "html": "artifacts", "docx": "documents", "xlsx": "spreadsheets"}.get(kind, "documents")
        return named_artifact_path(self.workspace / folder, topic, kind)

    async def _remember(self, path: Path, action: str, project_scoped: bool) -> None:
        await upsert_preference(self.db_path, LAST_DOC_KEY, str(path), source="document")
        await record_structured_artifact(
            self.db_path,
            DIRECT_DOC_RUN_ID,
            local_artifact(_artifact_kind(path), str(path), action, "document_actions"),
        )
        project = await active_project(self.db_path) if project_scoped else None
        if project:
            await remember_project_note(self.db_path, project.path, "document", f"{action}: {path.name}")

    async def _finish_excel(self, path: Path, label: str, topic: str, project_scoped: bool, channel: str) -> str:
        local_qa = await asyncio.to_thread(validate_xlsx_path, path, topic)
        self.last_model_lane += " + local Excel QA"
        review_qa = await review_artifact_quality(self.db_path, "xlsx", topic, await asyncio.to_thread(extract_xlsx_text, path))
        if review_qa.review_model:
            self.last_model_lane += " + Claude Excel review"
        elif review_qa.warnings:
            self.last_model_lane += " + Claude Excel review skipped"
        quality = local_qa.merge(review_qa)
        await self._remember(path, f"Created {label}: {quality.summary}", project_scoped)
        if not quality.passed:
            return await self._draft_with_issues(label, path, channel, "Microsoft Excel", quality.short_issue_text())
        return await self._done(label, path, channel, "Microsoft Excel")

    async def _draft_with_issues(self, label: str, path: Path, channel: str, app_name: str | None, issues: str) -> str:
        message = f"I created a {label} at {path}, but QA found: {issues}. I’m keeping it as a draft."
        if channel == "imac":
            try:
                opened_app = await asyncio.to_thread(open_created_file, path, self.bridge, app_name)
                suffix = f" in {opened_app}" if opened_app else ""
                return f"{message} I opened it on the iMac{suffix}."
            except Exception as exc:
                return f"{message} I could not open it: {exc}"
        return _attach(message, path, channel)

    async def _done(self, label: str, path: Path, channel: str, app_name: str | None) -> str:
        article = "an" if label.lower().startswith("excel") else "a"
        message = f"Done. I created {article} {label} at {path}."
        if channel == "imac":
            try:
                opened_app = await asyncio.to_thread(open_created_file, path, self.bridge, app_name)
                suffix = f" in {opened_app}" if opened_app else ""
                return f"{message} I opened it on the iMac{suffix}."
            except Exception as exc:
                return f"{message} I could not open it: {exc}"
        return _attach(f"Done. I created {article} {label}.", path, channel)

    async def _markdown_target(self) -> Path | None:
        raw = await get_preference(self.db_path, LAST_DOC_KEY)
        return Path(raw) if raw else None


def _quick_request(topic: str) -> bool:
    low = topic.lower()
    return any(word in low for word in ("quick", "rough", "starter", "simple", "just draft"))


def _strip_quality_words(topic: str) -> str:
    return re.sub(r"\b(quick|rough|starter|simple|just draft)\b", " ", topic, flags=re.I).strip(" .") or topic


def _kampung_ai_cost_topic(topic: str) -> bool:
    low = topic.lower()
    return "kampung ai" in low and any(word in low for word in ("cost", "budget", "spend", "usage", "tracker"))


def _excel_lane(topic: str) -> str:
    if _kampung_ai_cost_topic(topic):
        return "Local Kampung AI cost tracker"
    if is_kampung_ai_testing_comparison(topic):
        return "Local Kampung AI testing comparison"
    return "Gemini Flash role-based spreadsheet draft"


def _budget_topic(topic: str) -> bool:
    return any(word in topic.lower() for word in ("budget", "budgeting", "expense", "cost", "trip"))


def _travel_budget_topic(topic: str) -> bool:
    low = topic.lower()
    return any(word in low for word in ("travel", "trip", "holiday", "vacation", "flight", "hotel", "airbnb")) and any(
        word in low for word in ("budget", "budgeting", "expense", "cost")
    )


def _budget_rows(topic: str) -> tuple[list[str], list[list[str]]]:
    rows = [
        ["Flights", "", "", "", "", "", "Add fare after search"],
        ["Accommodation", "", "", "", "", "", "Split by city if needed"],
        ["Local Transport", "", "", "", "", "", "Trains, subway, buses, airport transfers"],
        ["Food", "", "", "", "", "", "Daily estimate"],
        ["Attractions", "", "", "", "", "", "Tickets and activities"],
        ["Shopping", "", "", "", "", "", "Optional"],
        ["Miscellaneous", "", "", "", "", "", "Buffer"],
        ["Total", "All categories", "=SUM(C2:C8)", "=SUM(D2:D8)", "=SUM(E2:E8)", "=SUM(F2:F8)", "Formula row"],
    ]
    lowered = topic.lower()
    if "tokyo" in lowered:
        rows[0][1] = "Tokyo flights or train"
        rows[1][1] = "Tokyo stay"
        rows[2][1] = "Tokyo metro, IC card, airport transfer"
    return ["Category", "Item", "Estimated JPY", "Estimated MYR", "Actual JPY", "Actual MYR", "Notes"], rows


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
