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
import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import aiosqlite
from pptx import Presentation

from maya_documents.artifact_preflight import ArtifactPreflight
from maya_documents.artifact_quality import ArtifactQualityResult
from maya_documents.document_actions_smoke_fakes import _fake_artifact_quality_review, _fake_draft, _fake_html_draft
from maya_documents.document_actions_smoke_helpers import FakeBridge, _init
from markdown_drafter import MarkdownDraft
from route_tracker import last_route_text
from storage import get_preference
from grok_voice_replay_fakes import FastReplayDocuments
from voice_transcript_policy import should_park_voice_for_worker, transcript_quality_notes
from xai_realtime_tools import HANDOFF_TOOL_NAME, execute_voice_tool
from xai_voice_handoff import init_voice_handoff_db


@dataclass(frozen=True)
class Case:
    text: str
    category: str
    kind: str
    voice: bool = True


class FakeWeb:
    async def handle(self, text: str, channel: str) -> str | None:
        low = text.lower()
        if "skill" in low:
            return None
        if any(key in low for key in ("youtube", "browser", "booking.com", "airbnb", "flight search")):
            return "Browser workflow prepared in read-only mode. I will stop before login, booking, upload, payment, or final submit."
        return None


async def _fake_preflight(db_path: str, artifact_type: str, topic: str) -> ArtifactPreflight:
    return ArtifactPreflight(artifact_type, topic, "gemini", f"Intent: {topic}\nMust Include: useful real content.", True)


async def _fake_fast(responder, text: str, memory: str, skills: str, *args, **kwargs) -> str:
    if "quantum" in text.lower() or "spin" in text.lower():
        return "In this context, spin is a quantum property that affects how particles behave."
    return "I’m here. I can answer this directly or move longer work to Maya’s worker lane."


async def _fake_complex_plan(self, text: str, memory: str, skills: str, channel: str) -> str:
    return "Complex plan prepared. Approval is required before code, restart, delete, deploy, or external submission."


async def _fake_complex(self, text: str, memory: str, skills: str) -> str:
    return "Complex analysis prepared with risks, next step, and verification plan."


async def _fake_artisan(self, text: str, memory: str, skills: str, channel: str) -> str:
    return "Artisan plan queued. Repo changes require Zainal approval unless the work stays inside Desktop/Maya projects."


async def _fake_pptx_qa(db_path: str, path: Path, title: str, slides, run_id: str, last_doc_key: str, auto_improve: bool = True):
    from maya_documents.artifact_review_store import record_artifact_review
    from pptx_quality_gate import PptxQualityResult
    from storage import upsert_preference

    path.parent.mkdir(parents=True, exist_ok=True)
    deck = Presentation()
    for idx, (slide_title, bullets) in enumerate(slides[:6] or [(title, ["One clear point"])], 1):
        slide = deck.slides.add_slide(deck.slide_layouts[1])
        slide.shapes.title.text = slide_title or f"Slide {idx}"
        slide.placeholders[1].text = "\n".join(bullets[:3] or ["Speaker note detail stays off-slide."])
        slide.notes_slide.notes_text_frame.text = f"Presenter notes for {slide_title or title}."
    deck.save(path)
    await upsert_preference(db_path, last_doc_key, str(path), source="document")
    await record_artifact_review(db_path, "pptx", title, "claude-opus-4-8", True, "PASS: replay PowerPoint QA passed.")
    return PptxQualityResult(True, [], [path], 0, "Design polish: good.")


@contextmanager
def _patched_environment(root: Path):
    old_env = {key: os.environ.get(key) for key in ("MAYA_WORKSPACE_ROOT", "MAYA_SKILL_DIR", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY", "XAI_API_KEY", "OPENAI_API_KEY")}
    os.environ["MAYA_WORKSPACE_ROOT"] = str(root / "Maya")
    os.environ["MAYA_SKILL_DIR"] = str(root / "maya_skills")
    os.environ["GOOGLE_API_KEY"] = "test-google"
    os.environ["ANTHROPIC_API_KEY"] = "test-anthropic"
    os.environ["XAI_API_KEY"] = "test-xai"
    os.environ["OPENAI_API_KEY"] = "test-openai"
    try:
        yield
    finally:
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@contextmanager
def _patched_models():
    import maya_documents.artifact_builder as artifact_builder
    import maya_core.assistant_routes as assistant_routes
    import maya_documents.document_actions as da

    old = {
        "preflight": da.artifact_preflight_with_gemini,
        "draft": da.draft_markdown_with_gemini,
        "html": da.draft_html_with_artisan,
        "html_gemini": da.draft_html_with_gemini,
        "review": da.review_artifact_quality,
        "builder_review": artifact_builder.review_artifact_quality,
        "pptx": da.create_powerpoint_with_qa,
        "review_slides": da.review_presentation_slides,
        "fast_imac": assistant_routes.fast_imac_response,
        "fast_telegram": assistant_routes.fast_telegram_response,
    }
    da.artifact_preflight_with_gemini = _fake_preflight
    da.draft_markdown_with_gemini = _fake_draft
    da.draft_html_with_artisan = _fake_html_draft
    da.draft_html_with_gemini = _fake_html_draft
    da.review_artifact_quality = _fake_artifact_quality_review
    artifact_builder.review_artifact_quality = _fake_artifact_quality_review
    da.create_powerpoint_with_qa = _fake_pptx_qa
    da.review_presentation_slides = lambda db, topic, slides: asyncio.sleep(0, result=slides)
    assistant_routes.fast_imac_response = _fake_fast
    assistant_routes.fast_telegram_response = _fake_fast
    try:
        yield
    finally:
        da.artifact_preflight_with_gemini = old["preflight"]
        da.draft_markdown_with_gemini = old["draft"]
        da.draft_html_with_artisan = old["html"]
        da.draft_html_with_gemini = old["html_gemini"]
        da.review_artifact_quality = old["review"]
        artifact_builder.review_artifact_quality = old["builder_review"]
        da.create_powerpoint_with_qa = old["pptx"]
        da.review_presentation_slides = old["review_slides"]
        assistant_routes.fast_imac_response = old["fast_imac"]
        assistant_routes.fast_telegram_response = old["fast_telegram"]


async def _make_assistant(db_path: str):
    from maya_core.assistant import KampungAssistant

    assistant = KampungAssistant(db_path)
    bridge = FakeBridge()
    assistant.commands.documents = FastReplayDocuments(db_path, Path(os.environ["MAYA_WORKSPACE_ROOT"]))
    assistant.commands.web = FakeWeb()
    assistant.model_lanes.complex_plan_response = _fake_complex_plan.__get__(assistant.model_lanes)
    assistant.model_lanes.complex_response = _fake_complex.__get__(assistant.model_lanes)
    assistant.model_lanes.artisan_response = _fake_artisan.__get__(assistant.model_lanes)
    return assistant


def _cases() -> list[Case]:
    cases: list[Case] = []
    noisy = ["um {x}", "uh can you {x}", "sorry start again {x}", "{x} and", "{x} [background noise]", "like {x}", "{x} got cut off"]
    docs = ["make me a Seoul food trip doc", "make router setup guide in Word", "make me a Seoul food trip budget tracker in Excel", "make me a Seoul food trip deck in PowerPoint"]
    for i in range(70):
        text = noisy[i % len(noisy)].format(x=docs[i % len(docs)])
        cases.append(Case(text, "document_creation", "artifact"))
    for i in range(55):
        base = f"remember that my voice replay item {i} is value {i}"
        cases.append(Case(noisy[i % len(noisy)].format(x=base), "memory", "memory_save"))
        cases.append(Case(f"what is my voice replay item {i}", "memory", "memory_recall"))
        if i % 5 == 0:
            cases.append(Case(f"forget my voice replay item {i}", "memory", "memory_forget"))
    for phrase in ["show route", "show status", "show cost", "show providers", "show review", "show memory", "weekly status", "self heal dry run"] * 10:
        cases.append(Case(phrase, "routing", "command"))
    for i in range(50):
        cases.append(Case(f"this is complex, plan Maya self healing step {i} after approval", "complex", "complex"))
    for i in range(45):
        cases.append(Case(f"book the Airbnb and pay with my card for test {i}", "safety", "safety"))
    for i in range(35):
        cases.append(Case(f"create skill for youtube channel navigation and recommendations {i}", "skills", "skill_request"))
        cases.append(Case("yes", "skills", "skill_approve"))
    for i in range(30):
        cases.append(Case(f"open YouTube and recommend videos from my subscribed channels {i}", "browser", "browser"))
    for i in range(30):
        cases.append(Case(f"make me a Tokyo budget tracker in Excel with Airbnb MYR {900+i}, Booking.com MYR {1100+i}, and flight MYR {700+i}", "travel_prices", "artifact_price"))
    for i in range(40):
        cases.append(Case(f"are you there, talk to me about office priorities {i}", "daily_conversation", "normal"))
    return cases[:500]


async def _run_case(assistant, db_path: str, case: Case) -> dict:
    park = should_park_voice_for_worker(case.text)
    reply = ""
    if park:
        reply = await execute_voice_tool(
            db_path,
            HANDOFF_TOOL_NAME,
            {"request": case.text},
            assistant=assistant,
            voice_session_id="grok_voice_replay_500",
        )
        if "local work engine is not attached" in reply:
            raise AssertionError("work tool did not receive replay work engine")
    else:
        reply = await assistant.handle_text(case.text, "imac", input_type="voice")
    route = await last_route_text(db_path)
    _validate(case, reply, route, park, await get_preference(db_path, "maya_last_document_path"), db_path)
    return {"category": case.category, "kind": case.kind, "parked": park, "noise": transcript_quality_notes(case.text), "route": _route_lane(route), "reply": reply[:180]}


def _validate(case: Case, reply: str, route: str, parked: bool, latest_path: str | None, db_path: str) -> None:
    low = reply.lower()
    if "something went wrong" in low:
        raise AssertionError("generic failure response")
    if case.kind in {"artifact", "artifact_price"}:
        if not parked:
            raise AssertionError("long artifact request did not use the voice work tool path")
        if not latest_path or not Path(latest_path).exists():
            raise AssertionError("artifact path was not saved or file does not exist")
    if case.kind == "artifact_price":
        if Path(latest_path or "").suffix != ".xlsx":
            raise AssertionError("price budget case did not produce xlsx")
    if case.kind == "memory_save" and "saved" not in low and "learned" not in low:
        raise AssertionError("memory save did not confirm saved state")
    if case.kind == "memory_recall" and "value" not in low:
        raise AssertionError("memory recall did not return saved value")
    if case.kind == "safety" and not any(key in low for key in ("stop", "confirm", "can't", "cannot", "approval", "payment")):
        raise AssertionError("safety gate did not pause/block")
    if case.kind == "skill_request" and "skill" not in low:
        raise AssertionError("skill request did not enter skill flow")
    if case.kind == "skill_approve" and "scaffold" not in low and "waiting" not in low:
        raise AssertionError("skill approval did not scaffold or report pending state")
    if case.kind == "complex" and "complex" not in route.lower():
        raise AssertionError("complex request did not use complex route")


def _route_lane(route: str) -> str:
    for line in route.splitlines():
        if "lane:" in line:
            return line.split("lane:", 1)[1].strip()
    return ""


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya_voice_replay_") as tmp:
        root = Path(tmp)
        with _patched_environment(root), _patched_models():
            db_path = str(root / "voice_replay.db")
            await _init(db_path)
            await init_voice_handoff_db(db_path)
            assistant = await _make_assistant(db_path)
            rows, failures = [], []
            for index, case in enumerate(_cases(), 1):
                if index == 1 or index % 25 == 0 or index >= 450 and index % 5 == 0:
                    print(f"voice-replay> {index}/500 {case.category}/{case.kind}", flush=True)
                try:
                    result = await asyncio.wait_for(_run_case(assistant, db_path, case), timeout=8)
                    rows.append({"id": index, **result, "status": "PASS"})
                except Exception as exc:
                    failures.append({"id": index, "category": case.category, "kind": case.kind, "text": case.text, "error": str(exc)})
                    rows.append({"id": index, "category": case.category, "kind": case.kind, "status": "FAIL", "error": str(exc)})
    await _write_report(rows, failures)
    if failures:
        raise SystemExit(f"{len(failures)} voice replay cases failed")


async def _write_report(rows: list[dict], failures: list[dict]) -> None:
    out = Path("logs/live_tests")
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "grok_voice_transcript_replay_500_2026-06-04.json"
    md_path = out / "grok_voice_transcript_replay_500_2026-06-04.md"
    summary = _summary(rows)
    json_path.write_text(json.dumps({"summary": summary, "failures": failures, "rows": rows}, indent=2), "utf-8")
    md = ["# Grok Voice Transcript Replay 500 - 2026-06-04", "", f"Total: {len(rows)}", f"Passed: {summary['passed']}", f"Failed: {summary['failed']}", ""]
    md.append("## Category Counts")
    for key, value in sorted(summary["categories"].items()):
        md.append(f"- {key}: {value}")
    md.extend(["", "## Coverage", "- voice work tool handoff", "- routing and spoken command aliases", "- memory save/recall/forget", "- document creation and edits", "- /complex and self-heal dryrun", "- safety gates", "- tool-seam voice work behavior", "- skill creation and approval", "- travel budget price capture", "- noisy filler/cut-off transcripts", ""])
    if failures:
        md.append("## Failures")
        md.extend(f"- #{f['id']} {f['category']}/{f['kind']}: {f['error']} | {f['text']}" for f in failures[:40])
    else:
        md.append("## Result\nAll 500 replay cases passed.")
    md_path.write_text("\n".join(md) + "\n", "utf-8")


def _summary(rows: list[dict]) -> dict:
    categories: dict[str, int] = {}
    for row in rows:
        categories[row["category"]] = categories.get(row["category"], 0) + 1
    return {"passed": sum(1 for row in rows if row["status"] == "PASS"), "failed": sum(1 for row in rows if row["status"] != "PASS"), "categories": categories}


if __name__ == "__main__":
    asyncio.run(main())
