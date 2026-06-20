from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from maya_documents.artifact_quality import extract_docx_text, validate_docx_path, validate_xlsx_path
from maya_core.storage import init_db
from maya_voice.xai_realtime_document_tools import execute_desktop_file_tool
from maya_documents.office_edit_helpers import pptx_outline


LOG_DIR = Path("logs/live_tests")
CASE_TIMEOUT_SECONDS = 150


@dataclass
class DocumentBatchCase:
    id: str
    kind: str
    prompt: str
    passed: bool
    created_path: str
    opened: bool
    summarized_content: bool
    route_lane: str
    duration_s: float
    evidence: str
    db_path: str


WORD_PROMPTS = [
    "Create a Word document about a nine day Almaty Kazakhstan hiking vacation plan for two adults with practical itinerary, packing, cost assumptions, risks, and next actions.",
    "Write a Word document about starting a small drone inspection company in Malaysia, including equipment, permits, staffing, pricing, workflow, and safety risks.",
    "Make a Word document about a Python CLI release checklist for Kampung AI, including tests, rollback, logs, and owner responsibilities.",
    "Create a Word proposal for a modern kampung homestay business, covering guest experience, operations, pricing, marketing, and risks.",
    "Write a Word brief about moving a small startup to Google Cloud, including architecture, cost control, security, monitoring, and migration steps.",
    "Create a Word document about a YouTube content strategy for an AI assistant channel, including audience, topics, format, schedule, and metrics.",
    "Make a Word checklist for a Japan trip emergency packing and preflight preparation plan, including documents, medicine, devices, and money.",
    "Write a Word troubleshooting guide for UniFi router setup with PuTTY, WAN setup, WiFi setup, diagnostics, and common mistakes.",
    "Create a Word workshop plan for a school robotics day, including objectives, materials, schedule, team roles, and assessment.",
    "Make a Word document about investor call meeting notes for Kampung AI, including agenda, questions, decisions, follow ups, and risks.",
]


EXCEL_PROMPTS = [
    "Create an Excel travel budget for a five day Seoul food trip for two people with flights, hotel, food, transport, shopping, attractions, actual cost, estimated cost, notes, and totals.",
    "Make an Excel monthly SaaS cost tracker for Kampung AI with provider, tool, owner, plan, estimated USD, actual USD, usage, renewal date, and savings notes.",
    "Create an Excel drone company equipment budget with item, quantity, unit cost MYR, total cost MYR, vendor, priority, status, and notes.",
    "Make an Excel coding sprint tracker for a browser skill project with task, owner, priority, status, estimate hours, actual hours, blocker, and next action.",
    "Create an Excel agriculture concern tracker for Malaysia with issue, state, severity, affected crop, evidence, mitigation, owner, and review date.",
    "Make an Excel family Ramadan grocery budget with category, item, estimated MYR, actual MYR, quantity, shop, variance, and notes.",
    "Create an Excel Google Cloud cost control sheet with service, project, monthly estimate USD, actual USD, alert threshold, owner, and optimization action.",
    "Make an Excel YouTube video research tracker with topic, channel, views, duration, published date, rating notes, watch priority, and summary.",
    "Create an Excel PowerPoint production tracker with deck, slide count, content owner, design status, QA status, deadline, and comments.",
    "Make an Excel home renovation budget for a modern kampung house with area, item, estimated MYR, actual MYR, contractor, priority, and notes.",
]


PPTX_PROMPTS = [
    "Create a PowerPoint about agriculture concerns in Malaysia with climate risk, labor shortage, fertilizer cost, water management, policy options, and a clear recommendation.",
    "Make a PowerPoint about an Almaty Kazakhstan hiking trip plan with route options, safety, budget, packing, itinerary, and why the trip is worth doing.",
    "Create a PowerPoint about browser automation skills for Maya, covering Google Search, Google Images, YouTube, Reddit, Google Flights, and safety boundaries.",
    "Make a PowerPoint about launching a drone inspection company in Malaysia with market, services, equipment, pricing, operations, and risks.",
    "Create a PowerPoint about modern kampung house design inspiration with materials, layout, climate response, cost tradeoffs, and visual direction.",
    "Make a PowerPoint about a coding architecture for Kampung AI with voice, browser skills, document tools, memory, safety, and provider routing.",
    "Create a PowerPoint about Google Cloud cost governance for a small AI startup with budget alerts, logging, security, and weekly review.",
    "Make a PowerPoint about YouTube learning strategy for AI builders with channel selection, video scoring, note taking, and practice workflow.",
    "Create a PowerPoint about a Japan travel planning workflow for Osaka and Kyoto with flight search, hotel comparison, Airbnb comparison, budget Excel, and final decision steps.",
    "Make a PowerPoint about school robotics workshop planning with learning goals, agenda, kits, team roles, judging, and post-event follow-up.",
]


async def main() -> None:
    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
    started = datetime.now().isoformat(timespec="seconds")
    batch_stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    cases: list[DocumentBatchCase] = []
    for kind, prompts in (("word", WORD_PROMPTS), ("excel", EXCEL_PROMPTS), ("pptx", PPTX_PROMPTS)):
        for idx, prompt in enumerate(prompts, 1):
            case_id = f"{kind}-{idx:02d}"
            db_path = str(LOG_DIR / f"imac_document_creation_batch_{batch_stamp}_{case_id}.db")
            await init_db(db_path)
            print(f"running {case_id}: {prompt}", flush=True)
            case = await _run_case(db_path, case_id, kind, prompt)
            cases.append(case)
            print(f"finished {case_id}: {'PASS' if case.passed else 'FAIL'} in {case.duration_s}s", flush=True)
            await asyncio.sleep(0.4)
    path = _write_log(started, cases)
    passed = sum(1 for case in cases if case.passed)
    print(f"imac_document_creation_batch_live: {passed}/{len(cases)} passed")
    print(f"log: {path}")
    if passed != len(cases):
        failed = "\n".join(f"{case.id}: {case.evidence}" for case in cases if not case.passed)
        raise AssertionError(failed)


async def _run_case(db_path: str, case_id: str, kind: str, prompt: str) -> DocumentBatchCase:
    started = time.monotonic()
    try:
        reply = await asyncio.wait_for(execute_desktop_file_tool(db_path, prompt), timeout=CASE_TIMEOUT_SECONDS)
        duration = round(time.monotonic() - started, 2)
        created = _extract_path(reply, kind)
        opened = "opened it on the imac" in reply.lower()
        summarized = "content summary:" in reply.lower()
        route_lane = await _latest_route_lane(db_path)
        validation = await _validate_created(kind, created, prompt)
        passed = bool(created and Path(created).exists() and opened and summarized and validation[0])
        evidence = _compact(f"{validation[1]} | {reply}")
        return DocumentBatchCase(case_id, kind, prompt, passed, created, opened, summarized, route_lane, duration, evidence, db_path)
    except Exception as exc:
        duration = round(time.monotonic() - started, 2)
        return DocumentBatchCase(case_id, kind, prompt, False, "", False, False, "", duration, f"{type(exc).__name__}: {exc}", db_path)


async def _validate_created(kind: str, path_text: str, prompt: str) -> tuple[bool, str]:
    if not path_text:
        return False, "no created path in reply"
    path = Path(path_text)
    if not path.exists():
        return False, f"path missing: {path}"
    try:
        if kind == "word":
            text = await asyncio.to_thread(extract_docx_text, path)
            local = await asyncio.to_thread(validate_docx_path, path, prompt)
            enough_text = len(text.split()) >= 180
            topic_ok = _topic_fit(prompt, text)
            # Local QA must pass outright. A long document with failing QA
            # (for example missing day headings) is a failure, not a pass.
            return enough_text and topic_ok and local.passed, (
                f"word chars={len(text)} words={len(text.split())} topic_fit={topic_ok} qa={local.summary} issues={local.issues[:3]}"
            )
        if kind == "excel":
            local = await asyncio.to_thread(validate_xlsx_path, path, prompt)
            return local.passed, f"excel qa={local.summary}"
        outline = await asyncio.to_thread(pptx_outline, path)
        slide_count = outline.lower().count("slide ")
        topic_ok = _topic_fit(prompt, outline)
        return slide_count >= 3 and len(outline) > 200 and topic_ok, f"pptx outline chars={len(outline)} slides={slide_count} topic_fit={topic_ok}"
    except Exception as exc:
        return False, f"validation error: {type(exc).__name__}: {exc}"


async def _latest_route_lane(db_path: str) -> str:
    try:
        import sqlite3

        def read() -> str:
            conn = sqlite3.connect(db_path)
            try:
                row = conn.execute(
                    "select lane from route_events order by id desc limit 1"
                ).fetchone()
            finally:
                conn.close()
            return str(row[0]) if row else ""

        return await asyncio.to_thread(read)
    except Exception:
        return ""


def _extract_path(reply: str, kind: str) -> str:
    suffix = {"word": "docx", "excel": "xlsx", "pptx": "pptx"}[kind]
    pattern = rf"(/Users/[^\n\r]+?\.{suffix})"
    match = re.search(pattern, reply)
    if not match:
        return ""
    return match.group(1).strip().rstrip(".")


def _write_log(started: str, cases: list[DocumentBatchCase]) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = LOG_DIR / f"imac_document_creation_batch_{stamp}.json"
    payload = {
        "started_at": started,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "passed": sum(1 for case in cases if case.passed),
        "total": len(cases),
        "cases": [asdict(case) for case in cases],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _compact(text: str, limit: int = 900) -> str:
    cleaned = " ".join(text.split())
    return cleaned[:limit]


def _topic_fit(prompt: str, extracted: str) -> bool:
    prompt_words = _topic_keywords(prompt)
    if not prompt_words:
        return True
    lowered = extracted.lower()
    hits = [word for word in prompt_words if re.search(rf"\b{re.escape(word)}\b", lowered)]
    required = 1 if len(prompt_words) <= 2 else 2
    return len(hits) >= required


def _topic_keywords(prompt: str) -> list[str]:
    lowered = prompt.lower()
    groups = (
        ("kazakhstan", ("kazakhstan", "almaty", "hiking", "mountain")),
        ("drone", ("drone", "inspection", "uav", "aerial")),
        ("kampung ai", ("kampung", "ai")),
        ("kampung homestay", ("kampung", "homestay", "guest")),
        ("google cloud", ("google", "cloud", "security", "migration")),
        ("browser", ("browser", "search", "images", "reddit", "youtube")),
        ("youtube", ("youtube", "channel", "video")),
        ("router", ("router", "unifi", "putty", "wifi")),
        ("emergency packing", ("japan", "packing", "documents", "medicine")),
        ("preflight preparation", ("japan", "packing", "documents", "devices")),
        ("japan", ("japan", "osaka", "kyoto", "flight", "hotel")),
        ("robotics", ("robotics", "workshop", "kits")),
        ("saas", ("saas", "provider", "renewal")),
        ("agriculture", ("agriculture", "crop", "fertilizer", "climate")),
        ("ramadan", ("ramadan", "grocery")),
        ("renovation", ("renovation", "contractor")),
        ("powerpoint production", ("powerpoint", "slide", "deck")),
    )
    for marker, keywords in groups:
        if marker in lowered:
            return list(keywords)
    stop = {
        "create", "make", "write", "word", "document", "powerpoint", "excel", "about", "with", "including",
        "for", "and", "the", "a", "an", "plan", "tracker", "budget", "draft", "small", "clear",
    }
    words = [word for word in re.findall(r"[a-z][a-z0-9]+", lowered) if word not in stop and len(word) >= 5]
    return words[:6]


if __name__ == "__main__":
    asyncio.run(main())
