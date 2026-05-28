from __future__ import annotations

import asyncio
import os
import tempfile
import zipfile
from pathlib import Path

from assistant import KampungAssistant
from context_layers import init_context_layers_db
from lesson_store import init_lesson_db
from project_store import active_project
from route_tracker import last_route_text
from routine_store import init_routine_db
from session_memory_store import init_session_memory_db
from skill_store import init_skill_db
from storage import init_db, upsert_preference
from telegram_delivery import split_file_markers
from markdown_drafter import MarkdownDraft, _apply_source_quality, should_ground_topic
from openpyxl import load_workbook


class FakeBridge:
    def __init__(self):
        self.opened: list[tuple[str, str | None]] = []

    def open_file(self, path: str, app_name: str | None = None) -> None:
        self.opened.append((path, app_name))


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-doc-actions-") as tmp:
        old_google = os.environ.pop("GOOGLE_API_KEY", None)
        os.environ["MAYA_WORKSPACE_ROOT"] = str(Path(tmp) / "Maya")
        db_path = str(Path(tmp) / "smoke.db")
        root = Path(tmp) / "projects"
        (root / "orchid-lab").mkdir(parents=True)
        os.environ["MAYA_PROJECT_ROOTS"] = str(root)
        await _init(db_path)
        await upsert_preference(db_path, "pref_no_dash", "no dash symbols in answers", source="smoke")
        import document_actions as da
        old_draft = da.draft_markdown_with_gemini
        old_html = da.draft_html_with_kimi
        old_html_fallback = da.draft_html_with_gemini
        old_html_review = da.review_html_app
        old_should = da.should_use_model_draft
        old_review = da.review_presentation_slides
        da.draft_markdown_with_gemini = _fake_draft
        da.draft_html_with_kimi = _fake_html_draft
        da.draft_html_with_gemini = _fake_html_fallback
        da.review_html_app = _fake_html_review
        da.should_use_model_draft = lambda topic: True
        da.review_presentation_slides = _fake_review
        assistant = KampungAssistant(db_path)
        bridge = FakeBridge()
        assistant.commands.documents.bridge = bridge
        assistant.commands.documents.workspace = Path(tmp) / "Maya"

        md = await assistant.handle_text("create an md file about router setup", "telegram")
        _require("router setup.md" not in md, "visible path was damaged by style cleanup")
        _, md_files = split_file_markers(md)
        _require(md_files and md_files[0].suffix == ".md" and md_files[0].exists(), "markdown file missing")
        md_text = md_files[0].read_text(encoding="utf-8")
        _require("WAN or internet port" in md_text, "router markdown content too generic")
        _require("dash style" in md_text and "dash - style" not in md_text, "markdown ignored no-dash preference")

        model_note = await assistant.handle_text("create an md file about new gemini 3.5", "telegram")
        _, model_files = split_file_markers(model_note)
        _require(model_files and model_files[0].exists(), "model note file missing")
        model_text = model_files[0].read_text(encoding="utf-8")
        _require("What To Verify" in model_text, "model note did not use research structure")
        _require("Setup Steps" not in model_text, "model note used wrong setup structure")
        _require(should_ground_topic("meta rayban display"), "current product topic was not grounded")
        write_me = await assistant.handle_text("write me an md file about hormuz street in malaysia", "telegram")
        _, write_me_files = split_file_markers(write_me)
        _require(write_me_files and write_me_files[0].suffix == ".md", "write me md wording did not create file")

        meraki = await assistant.handle_text("draft a network config for a router in md file for meraki", "telegram")
        _, meraki_files = split_file_markers(meraki)
        _require(meraki_files and meraki_files[0].exists(), "draft in md wording did not create file")
        _require("meraki" in meraki_files[0].name, "meraki file name missing topic")

        html = await assistant.handle_text("Make me a html file for an app like wonderlog", "telegram")
        html_text, html_files = split_file_markers(html)
        _require(html_files and html_files[0].suffix == ".html", "html request did not attach an html file")
        _require("```html" not in html_text and "<!DOCTYPE html>" not in html_text, "html source was pasted into chat")
        html_file_text = html_files[0].read_text(encoding="utf-8")
        _require("<!DOCTYPE html>" in html_file_text, "html file content missing doctype")
        _require("<script" in html_file_text and "<button" in html_file_text, "html file was not an interactive app")
        _require("<pre>" not in html_file_text and "### Role" not in html_file_text, "html app should not be a spec wrapper")
        _require("Reviewed by Claude" in html_file_text, "html app was not reviewed")
        html_route = await last_route_text(db_path)
        _require("Kimi HTML app builder + Claude HTML review + local HTML QA" in html_route, "html app should use Kimi plus Claude plus local QA lane")

        typo_html = await assistant.handle_text("ake me a html file for a travel planner app", "telegram")
        typo_text, typo_files = split_file_markers(typo_html)
        _require(typo_files and typo_files[0].suffix == ".html", "missing-leading-m html request did not create file")
        _require("<!DOCTYPE html>" not in typo_text, "typo html request pasted source into chat")

        docx = await assistant.handle_text("write a Word document about router setup", "telegram")
        _, docx_files = split_file_markers(docx)
        _require(docx_files and _zip_has(docx_files[0], "word/document.xml"), "docx file missing")
        _require(_zip_text(docx_files[0], "word/document.xml").count("WAN or internet port"), "docx used template content")
        _require("dash style" in _zip_text(docx_files[0], "word/document.xml"), "docx ignored no-dash preference")
        voice_word = await assistant.handle_text("Give me a two days work document for Q23", "telegram", input_type="voice note")
        _, voice_word_files = split_file_markers(voice_word)
        _require(voice_word_files and _zip_has(voice_word_files[0], "word/document.xml"), "voice/STT work document wording should create docx")
        travel_doc = await assistant.handle_text("write a Word document about a pre-travel Maya testing checklist", "telegram")
        _, travel_files = split_file_markers(travel_doc)
        travel_text = _zip_text(travel_files[0], "word/document.xml") if travel_files else ""
        _require("Model generated content" in travel_text, "Maya testing doc did not use Gemini role-based drafting")
        _require("Autodesk" not in travel_text, "Maya testing doc drifted to Autodesk Maya")

        deck = await assistant.handle_text("make presentation on router setup", "telegram")
        _, deck_files = split_file_markers(deck)
        _require(deck_files and _zip_has(deck_files[0], "ppt/presentation.xml"), "pptx file missing")
        _require(_office_can_open(deck_files[0]), "pptx should open without repair")
        deck_text = " ".join(_zip_text(deck_files[0], name) for name in _slide_members(deck_files[0]))
        _require("Key concept 1" not in deck_text, "pptx used placeholder content")
        _require("Reviewed narrative" in deck_text, "pptx did not use review content")
        _require("Review dash" in deck_text, "pptx ignored no-dash preference")
        _require("monocular HUD" not in deck_text, "pptx QA leaked Ray-Ban revision content")
        _require("Visual QA passed" in deck, "pptx did not report QA result")
        powerpoint = await assistant.handle_text("make me a PowerPoint about Kampung AI Telegram features", "telegram")
        _, powerpoint_files = split_file_markers(powerpoint)
        _require(powerpoint_files and _zip_has(powerpoint_files[0], "ppt/presentation.xml"), "PowerPoint wording did not create a pptx file")

        await assistant.handle_text("open project Orchid Lab", "telegram")
        project = await active_project(db_path)
        _require(project is not None, "project did not open")
        scoped = await assistant.handle_text("create an md file for this project about setup", "telegram")
        _, scoped_files = split_file_markers(scoped)
        _require(
            scoped_files and scoped_files[0].parent.resolve() == (project.path / "docs").resolve(),
            "project md not in docs",
        )

        updated = await assistant.handle_text("update this markdown with add cable notes", "telegram")
        _require("updated the Markdown file" in updated, "markdown update failed")
        _require("add cable notes" in scoped_files[0].read_text(encoding="utf-8"), "markdown update not written")

        blocked = await assistant.handle_text("create an md file about API key token", "telegram")
        _require("can't expose sensitive" in blocked.lower(), "sensitive document was not blocked")

        imac = await assistant.handle_text("write a Word document about desk setup", "imac")
        _require("opened it on the iMac" in imac and bridge.opened, "iMac document did not open")
        imac_md = await assistant.handle_text("create an md file about imac context test", "imac")
        _require("opened it on the iMac in Cursor" in imac_md, "iMac markdown did not prefer Cursor")
        imac_budget = await assistant.handle_text("make me a budgeting Excel for this trip", "imac")
        _require("Excel budget tracker" in imac_budget and bridge.opened[-1][1] == "Microsoft Excel", "iMac budget Excel did not open")
        budget = await assistant.handle_text("make me an Excel budget tracker for Tokyo from June 1 to June 3 for 1 person", "telegram")
        _, budget_files = split_file_markers(budget)
        _require(budget_files and budget_files[0].name.startswith("tokyo-budget-tracker"), "budget tracker filename should be concise")
        budget_text = _workbook_text(budget_files[0])
        _require("Estimated JPY" in budget_text and "Actual JPY" in budget_text, "budget tracker should have editable budget columns")
        _require("Role And Assumptions" not in budget_text, "budget tracker should not be a notes spreadsheet")
        sheet = await assistant.handle_text("make an Excel comparison sheet for router setup and mesh wifi", "telegram")
        _, sheet_files = split_file_markers(sheet)
        _require(sheet_files and _zip_has(sheet_files[0], "xl/worksheets/sheet1.xml"), "xlsx file missing")
        sheet_text = _zip_text(sheet_files[0], "xl/worksheets/sheet1.xml")
        _require("Option 1" not in sheet_text, "xlsx used placeholder content")
        _require("dash style" in sheet_text, "xlsx ignored no-dash preference")
        _require(_office_can_open(sheet_files[0]), "xlsx should open without repair")
        cost_sheet = await assistant.handle_text("make an Excel tracker for Kampung AI cost", "telegram")
        _, cost_files = split_file_markers(cost_sheet)
        _require(cost_files and _zip_has(cost_files[0], "xl/workbook.xml"), "cost xlsx missing workbook")
        cost_text = _workbook_text(cost_files[0])
        _require("Grok Voice Agent" in cost_text, "cost xlsx did not use local cost lanes")
        _require("Malaysian Ministry" not in cost_text, "cost xlsx used wrong public topic")
        try:
            await _model_draft_smoke(db_path)
            await _failure_smoke(db_path)
            _source_quality_smoke()
            print("document_actions_smoke: ok")
        finally:
            da.draft_markdown_with_gemini = old_draft
            da.draft_html_with_kimi = old_html
            da.draft_html_with_gemini = old_html_fallback
            da.review_html_app = old_html_review
            da.should_use_model_draft = old_should
            da.review_presentation_slides = old_review
            if old_google:
                os.environ["GOOGLE_API_KEY"] = old_google


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)
    await init_session_memory_db(db_path)
    await init_context_layers_db(db_path)


def _zip_has(path: Path, member: str) -> bool:
    with zipfile.ZipFile(path) as archive:
        return member in archive.namelist()


def _zip_text(path: Path, member: str) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read(member).decode("utf-8", errors="ignore")


def _workbook_text(path: Path) -> str:
    book = load_workbook(path, data_only=False)
    values = []
    for sheet in book.worksheets:
        for row in sheet.iter_rows(values_only=True):
            values.extend(str(item) for item in row if item is not None)
    return "\n".join(values)


def _slide_members(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        return [name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def _model_draft_smoke(db_path: str) -> None:
    import document_actions as da
    from route_tracker import last_route_text

    old_draft = da.draft_markdown_with_gemini
    old_should = da.should_use_model_draft

    try:
        da.draft_markdown_with_gemini = _fake_draft
        da.should_use_model_draft = lambda topic: True
        router = da.DocumentActionRouter(db_path, workspace=Path(os.environ["MAYA_WORKSPACE_ROOT"]))
        reply = await router.handle("create an md file about new gemini 3.5", "telegram")
        _require(reply and "[file:" in reply, "model draft did not attach file")
        _require(router.last_model_lane == "Gemini Flash grounded role-based document draft", "model draft lane not recorded")
        _require(router.last_cost_recorded is True, "model draft cost not recorded")
        assistant = KampungAssistant(db_path)
        response = await assistant.handle_text("create an md file about new gemini 3.5", "telegram")
        _require("[file:" in response, "assistant model draft did not attach file")
        route = await last_route_text(db_path)
        _require("Gemini Flash grounded role-based document draft" in route, "assistant route did not expose model draft lane")
        _require("cost recorded: yes" in route, "assistant route did not record model draft cost")

        async def fake_grounded(db_path: str, topic: str) -> MarkdownDraft:
            return MarkdownDraft("# New Gemini 3.5\n\n## Sources\n\n1) Google: https://ai.google.dev\n", grounded=True)

        da.draft_markdown_with_gemini = fake_grounded
        grounded_router = da.DocumentActionRouter(db_path, workspace=Path(os.environ["MAYA_WORKSPACE_ROOT"]))
        grounded_reply = await grounded_router.handle("create an md file about latest gemini", "telegram")
        _require(grounded_reply and "[file:" in grounded_reply, "grounded draft did not attach file")
        _require(grounded_router.last_model_lane == "Gemini Flash grounded role-based document draft", "grounded lane not recorded")
    finally:
        da.draft_markdown_with_gemini = old_draft
        da.should_use_model_draft = old_should

async def _failure_smoke(db_path: str) -> None:
    import document_actions as da

    old_draft = da.draft_markdown_with_gemini
    old_html = da.draft_html_with_kimi
    old_fallback = da.draft_html_with_gemini
    old_review = da.review_html_app

    async def fail_draft(db_path: str, topic: str) -> MarkdownDraft:
        raise RuntimeError("429 RESOURCE_EXHAUSTED")

    async def timeout_html(db_path: str, topic: str) -> MarkdownDraft:
        raise TimeoutError("Kimi timed out")

    async def no_html(db_path: str, topic: str) -> MarkdownDraft | None:
        return None

    async def no_review(db_path: str, topic: str, html: str):
        return html, "skipped"

    async def broken_review(db_path: str, topic: str, html: str):
        return "<!DOCTYPE html>\n<html><head><style>body{", "reviewed"

    try:
        da.draft_markdown_with_gemini = fail_draft
        da.review_html_app = no_review
        router = da.DocumentActionRouter(db_path, workspace=Path(os.environ["MAYA_WORKSPACE_ROOT"]))
        before = set(Path(os.environ["MAYA_WORKSPACE_ROOT"]).joinpath("notes").glob("quota-test*.md"))
        reply = await router.handle("create an md file about quota test", "telegram")
        after = set(Path(os.environ["MAYA_WORKSPACE_ROOT"]).joinpath("notes").glob("quota-test*.md"))
        _require("No file was created" in (reply or ""), "quota failure should not create fake file")
        _require(before == after, "quota failure created a file")
        da.draft_html_with_kimi = timeout_html
        da.draft_html_with_gemini = _fake_html_fallback
        fallback_reply = await router.handle("make me a html file for a travel planner app", "telegram")
        _require("[file:" in (fallback_reply or ""), "Gemini should take over when Kimi times out")
        _require(
            router.last_model_lane == "Kimi HTML timeout -> Gemini Flash HTML fallback + local HTML QA",
            "fallback lane should record the Kimi timeout before Gemini takeover",
        )
        da.draft_html_with_gemini = no_html
        html_reply = await router.handle("make me a html file for a travel planner app", "telegram")
        _require("Kimi and Gemini" in (html_reply or ""), "double HTML failure should be reported")
        _require("No file was created" in (html_reply or ""), "Kimi timeout should not claim a file")
        da.draft_html_with_kimi = _fake_html_draft
        da.draft_html_with_gemini = _fake_html_fallback
        da.review_html_app = broken_review
        broken_reply = await router.handle("make me a html file for a broken review check app", "telegram")
        _, broken_files = split_file_markers(broken_reply or "")
        _require(broken_files and broken_files[0].exists(), "broken review should still create original html")
        broken_text = broken_files[0].read_text(encoding="utf-8")
        _require("<script" in broken_text and "<button" in broken_text, "broken review replaced the usable original")
        _require(
            router.last_model_lane == "Kimi HTML app builder + Claude HTML review rejected + local HTML QA",
            "broken Claude review should be marked rejected",
        )
        da.review_html_app = same_review
        same_reply = await router.handle("make me a html file for a same review check app", "telegram")
        _require("[file:" in (same_reply or ""), "same review should still create html")
        _require(
            router.last_model_lane == "Kimi HTML app builder + Claude HTML review + local HTML QA",
            "valid same Claude review should be recorded",
        )
    finally:
        da.draft_markdown_with_gemini = old_draft
        da.draft_html_with_kimi = old_html
        da.draft_html_with_gemini = old_fallback
        da.review_html_app = old_review

async def _fake_draft(db_path: str, topic: str) -> MarkdownDraft:
    lowered = topic.lower()
    if "router" in lowered:
        return MarkdownDraft("# Router Setup\n\n## Real Draft\n\n1) Connect the WAN or internet port.\n2) Keep dash - style clean.\n")
    if "gemini" in lowered or "latest" in lowered:
        return MarkdownDraft("# New Gemini 3.5\n\n## What To Verify\n\n1) Check official sources.\n\n## Sources\n\n1) Google: https://ai.google.dev\n", grounded=True)
    if "html" in lowered or "wonderlog" in lowered:
        return MarkdownDraft("<!DOCTYPE html>\n<html lang=\"en\"><head><title>Wonderlog Style App</title></head><body><main>Trip planner</main></body></html>\n")
    return MarkdownDraft(f"# {topic.title()}\n\n## Real Draft\n\n1) Model generated content.\n")

async def _fake_html_draft(db_path: str, topic: str) -> MarkdownDraft:
    return MarkdownDraft(
        "<!DOCTYPE html>\n"
        "<html lang=\"en\"><head><title>Travel Planner</title><style>body{font-family:system-ui}</style></head>"
        "<body><main><h1>Travel Planner</h1><input id=\"item\"><button id=\"add\">Add</button><ul id=\"list\"></ul></main>"
        "<script>document.getElementById('add').addEventListener('click',()=>{const li=document.createElement('li');li.textContent=document.getElementById('item').value;document.getElementById('list').appendChild(li);localStorage.setItem('travelPlanner',document.getElementById('list').textContent);});</script>"
        "</body></html>\n"
    )

async def _fake_html_fallback(db_path: str, topic: str) -> MarkdownDraft:
    return MarkdownDraft(
        "<!DOCTYPE html>\n"
        "<html lang=\"en\"><head><title>Fallback Planner</title><style>body{font-family:system-ui}</style></head>"
        "<body><main><input id=\"city\"><button id=\"save\">Save</button></main>"
        "<script>document.getElementById('save').addEventListener('click',()=>localStorage.setItem('city',document.getElementById('city').value));</script>"
        "</body></html>\n"
    )

async def _fake_html_review(db_path: str, topic: str, html: str):
    return html.replace("</main>", "<p>Reviewed by Claude</p></main>"), "reviewed"

async def same_review(db_path: str, topic: str, html: str):
    return html, "reviewed"

async def _fake_review(db_path: str, topic: str, slides):
    return [("Reviewed narrative", ["WAN or internet port", "Review - dash"])]

def _office_can_open(path: Path) -> bool:
    if path.suffix == ".pptx":
        from pptx import Presentation
        Presentation(path)
        return True
    if path.suffix == ".xlsx":
        from openpyxl import load_workbook
        load_workbook(path)
        return True
    if path.suffix == ".docx":
        from docx import Document
        Document(path)
        return True
    return False

def _source_quality_smoke() -> None:
    text = "# Gemini\n\n## Overview\n\n1) Draft.\n\n### Sources\n\n1) Old source\n"
    sources = [
        ("Google AI", "https://ai.google.dev/gemini-api/docs"),
        ("simonwillison.net", "https://vertexaisearch.cloud.google.com/grounding-api-redirect/fake"),
        ("meta.com", "https://vertexaisearch.cloud.google.com/grounding-api-redirect/fake2"),
    ]
    cleaned = _apply_source_quality(text, sources)
    _require(cleaned.count("## Sources") == 1, "source section duplicated")
    _require("### Sources" not in cleaned, "model source heading survived")
    _require("### Official Sources" in cleaned, "official sources not labeled")
    _require("### Third Party Sources" in cleaned, "third party sources not labeled")
    _require("simonwillison.net" in cleaned, "redirected third party source missing")
    _require("meta.com" in cleaned.split("### Third Party Sources")[0], "official redirect title not recognized")
    _require("Old source" not in cleaned, "old model sources were not replaced")


if __name__ == "__main__":
    asyncio.run(main())
