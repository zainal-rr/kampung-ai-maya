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
from pathlib import Path

from maya_documents.document_actions_smoke_helpers import _init
from tests.replays.grok_voice_transcript_replay_500 import Case, _cases as base_cases
from tests.replays.grok_voice_transcript_replay_500 import _make_assistant, _patched_environment, _patched_models, _run_case
from xai_voice_handoff import init_voice_handoff_db


REPORT_JSON = Path("logs/live_tests/maya_voice_transcript_replay_700_2026-06-04.json")
REPORT_MD = Path("logs/live_tests/maya_voice_transcript_replay_700_2026-06-04.md")


def cases() -> list[Case]:
    rows = list(base_cases())
    extra: list[Case] = []
    daily = [
        "um are you there, talk to me about office priorities today",
        "sorry start again can you explain quantum computing simply",
        "what is spin in that quantum computing context",
        "show status",
        "show route",
    ]
    for i in range(20):
        extra.append(Case(daily[i % len(daily)], "daily_conversation", "normal"))
    for i in range(30):
        extra.append(Case(f"make me a Seoul food trip doc with transit notes and recommendations {i}", "document_creation", "artifact"))
        extra.append(Case(f"make me an Excel budget tracker with Airbnb MYR {900+i}, Booking.com MYR {1100+i}, and flight MYR {700+i}", "travel_prices", "artifact_price"))
    for i in range(30):
        extra.append(Case(f"this is complex self heal Maya after approval and show rollback plan {i}", "complex", "complex"))
    for i in range(25):
        extra.append(Case(f"open YouTube and recommend what I should watch from a channel about AI tools {i}", "browser", "browser"))
    for i in range(25):
        extra.append(Case(f"book Airbnb and pay with my card but stop before final submit {i}", "safety", "safety"))
    for i in range(20):
        extra.append(Case(f"create skill for browser youtube channel navigation {i}", "skills", "skill_request"))
        extra.append(Case("yes", "skills", "skill_approve"))
    for i in range(20):
        extra.append(Case(f"remember that my Maya voice learning canary {i} is stable {i}", "memory", "memory_save"))
        extra.append(Case(f"what is my Maya voice learning canary {i}", "memory", "memory_recall"))
    return (rows + extra)[:700]


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya_voice_replay_700_") as tmp:
        root = Path(tmp)
        with _patched_environment(root), _patched_models():
            db_path = str(root / "maya_voice_replay_700.db")
            await _init(db_path)
            await init_voice_handoff_db(db_path)
            assistant = await _make_assistant(db_path)
            rows, failures = [], []
            for index, case in enumerate(cases(), 1):
                if index == 1 or index % 25 == 0 or index >= 650 and index % 10 == 0:
                    print(f"maya-voice-replay> {index}/700 {case.category}/{case.kind}", flush=True)
                try:
                    result = await asyncio.wait_for(_run_case(assistant, db_path, case), timeout=8)
                    rows.append({"id": index, **result, "status": "PASS"})
                except Exception as exc:
                    failure = {"id": index, "category": case.category, "kind": case.kind, "text": case.text, "error": str(exc)}
                    failures.append(failure)
                    rows.append({"id": index, "category": case.category, "kind": case.kind, "status": "FAIL", "error": str(exc)})
            _write_report(rows, failures)
            if failures:
                raise SystemExit(f"{len(failures)} Maya voice transcript replay cases failed")


def _write_report(rows: list[dict], failures: list[dict]) -> None:
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    summary = _summary(rows)
    REPORT_JSON.write_text(json.dumps({"summary": summary, "failures": failures, "rows": rows}, indent=2), "utf-8")
    md = ["# Maya Voice Transcript Replay 700 - 2026-06-04", "", f"Total: {len(rows)}", f"Passed: {summary['passed']}", f"Failed: {summary['failed']}", "", "## Category Counts"]
    for key, value in sorted(summary["categories"].items()):
        md.append(f"- {key}: {value}")
    md.extend(["", "## What This Proves", "- Transcripts were sent through Maya's assistant pipeline as voice input.", "- Long work was parked through the Grok handoff tool before Maya's worker lane handled it.", "- Memory, documents, `/complex`, skills, safety, browser routing, travel prices, daily chat, and slashless commands were exercised.", "", "## Boundary", "This is still deterministic/local replay. It does not prove physical microphone, xAI websocket, Ara speaker output, live paid billing, Telegram upload, Bambu print execution, Omi, or Mudra."])
    if failures:
        md.extend(["", "## Failures"])
        md.extend(f"- #{f['id']} {f['category']}/{f['kind']}: {f['error']} | {f['text']}" for f in failures[:50])
    REPORT_MD.write_text("\n".join(md) + "\n", "utf-8")


def _summary(rows: list[dict]) -> dict:
    categories: dict[str, int] = {}
    for row in rows:
        categories[row["category"]] = categories.get(row["category"], 0) + 1
    return {"passed": sum(1 for row in rows if row["status"] == "PASS"), "failed": sum(1 for row in rows if row["status"] != "PASS"), "categories": categories}


if __name__ == "__main__":
    os.environ.setdefault("MAYA_REPLAY_MODE", "1")
    asyncio.run(main())
