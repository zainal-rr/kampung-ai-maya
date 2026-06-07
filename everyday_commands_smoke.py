from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from assistant import KampungAssistant
from context_layers import init_context_layers_db
from lesson_store import init_lesson_db
from office_modern_files import create_docx, create_pptx
from everyday_commands import EverydayCommandRouter
from harness_artifact_store import record_structured_artifact
from harness_models import local_artifact
from route_tracker import last_route_text
from routine_store import init_routine_db
from session_memory_store import init_session_memory_db
from skill_store import init_skill_db
from storage import init_db, upsert_preference


class FakeBridge:
    def __init__(self):
        self.opened: list[tuple[str, str | None]] = []

    def open_file(self, path: str, app_name: str | None = None) -> None:
        self.opened.append((path, app_name))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-everyday-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)
        path = Path(tmp) / "Maya" / "presentations" / "kampung-ai-telegram-features-v1.pptx"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"pptx")
        await upsert_preference(db_path, "maya_last_document_path", str(path), source="document")
        await record_structured_artifact(
            db_path,
            "direct_document_actions",
            local_artifact("presentation", str(path), "PowerPoint QA: Visual QA passed.", "smoke"),
        )
        bridge = FakeBridge()
        router = EverydayCommandRouter(db_path, bridge)  # type: ignore[arg-type]

        reply = await router.handle("what was the last document you created?", "telegram")
        _require(reply is not None and str(path) in reply, "latest document reply should include exact saved path")
        _require("exists on iMac: yes" in reply, "latest document reply should confirm existing local file")
        _require("PowerPoint QA" in reply, "latest document reply should include artifact summary")
        voice_style_reply = await router.handle("what document did you just create?", "telegram")
        _require(
            voice_style_reply is not None and str(path) in voice_style_reply,
            "voice-style recent document recall should include exact saved path",
        )
        just_now_reply = await router.handle("what document did you create just now?", "telegram")
        _require(
            just_now_reply is not None and str(path) in just_now_reply,
            "just-now recent document recall should include exact saved path",
        )

        telegram_open = await router.handle("open the last document", "telegram")
        _require(telegram_open is not None and f"[file:{path}]" in telegram_open, "Telegram open should attach exact last document")
        telegram_send = await router.handle("send me the last document", "telegram")
        _require(telegram_send is not None and f"[file:{path}]" in telegram_send, "Telegram send should attach exact last document")

        draft_path = Path(tmp) / "Maya" / "presentations" / "rejected-quality-draft-v1.pptx"
        draft_path.write_bytes(b"pptx")
        await upsert_preference(db_path, "maya_last_draft_document_path", str(draft_path), source="document")
        rough_reply = await router.handle("give me the rough draft if any", "telegram")
        _require(rough_reply is not None and f"[file:{draft_path}]" in rough_reply, "rough draft retrieval should attach saved draft")
        _require(router.last_reason == "draft document", "rough draft retrieval should use draft-document route")
        creation_reply = await router.handle("draft the document for tomorrow", "telegram")
        _require(creation_reply is None, "creation-style draft prompt should not be treated as latest-draft retrieval")

        imac_open = await router.handle("open the last document", "imac")
        _require(imac_open is not None and "opened" in imac_open.lower(), "iMac open should open the exact last document")
        _require(bridge.opened[-1][0] == str(path), "iMac opened the wrong latest document")

        real_deck = Path(tmp) / "Maya" / "presentations" / "seoul-food-trip-deck-v14.pptx"
        create_pptx(
            real_deck,
            "Seoul Food Trip Deck",
            [
                ("Seoul In 48 Hours", ["Food-first route", "Dark editorial guide"]),
                ("Anchor Each Day Around One Meal", ["Day 1 market classics", "Day 2 cafe and BBQ"]),
                ("Follow The Neighborhood Spine", ["Jongno market", "Myeongdong lunch", "Seongsu cafe block"]),
                ("Save The Splurge For Dinner", ["KRW daily budget", "One splurge dinner"]),
                ("Queue Tools Protect Plan", ["Naver Maps", "CatchTable reservation"]),
                ("Leave With A Ready Plan", ["Book anchor meals", "Keep transit simple"]),
            ],
        )
        await upsert_preference(db_path, "maya_last_document_path", str(real_deck), source="document")
        await record_structured_artifact(
            db_path,
            "final_pptx",
            local_artifact("presentation", str(real_deck), "PowerPoint QA: Visual QA passed.", "document_actions"),
        )
        await record_structured_artifact(
            db_path,
            "stale_pptx_polish",
            local_artifact(
                "presentation",
                str(real_deck),
                "Design polish: draft level. Slide 3 has incomplete fragments and slides 4 5 repeat filler labels.",
                "pptx_polish_review",
            ),
        )
        deck_send = await router.handle("send me the last document", "telegram")
        _require(deck_send is not None and f"[file:{real_deck}]" in deck_send, "latest PPTX send should attach exact deck")
        _require("draft level" not in deck_send.lower(), "latest PPTX summary should ignore stale draft-level polish rows")
        _require("PowerPoint deck with 6 slides" in deck_send, "latest PPTX summary should read the actual PPTX file")
        _require("Seoul In 48 Hours" in deck_send, "latest PPTX summary should include deck slide titles")
        _require("Speaker notes are present on all slides" in deck_send, "latest PPTX summary should mention presenter notes")

        doc_path = Path(tmp) / "Maya" / "documents" / "two-days-kyoto-trip-v1.docx"
        create_docx(
            doc_path,
            "Two Days Kyoto Trip",
            [
                ("Role and Assumptions", ["Role: I am coordinating a short Kyoto trip."]),
                ("Day 1: Higashiyama and Gion", ["Arrival at Kyoto Station, Kiyomizu dera, and dinner at Pontocho."]),
                ("Day 2: Arashiyama and Central Kyoto", ["Morning bamboo grove, Nishiki Market, and departure planning."]),
            ],
        )
        await upsert_preference(db_path, "maya_last_document_path", str(doc_path), source="document")
        doc_reply = await router.handle("what document did you just create?", "telegram")
        _require(doc_reply is not None and "two-day Kyoto trip plan" in doc_reply, "docx summary should use a natural document title")
        _require("day 1: Higashiyama" in doc_reply, "docx summary should include a useful itinerary heading")
        _require("Arrival at Kyoto Station" in doc_reply, "docx summary should include a concrete itinerary detail")
        assistant = KampungAssistant(db_path)
        voice_reply = await assistant.handle_text("what is the last document", "telegram", input_type="voice note")
        _require(str(doc_path) in voice_reply, "voice last-document reply should include visible path text")
        _require("Last document:" in voice_reply, "voice last-document reply should keep text metadata visible")
        _require("two-day Kyoto trip plan" in voice_reply, "voice last-document reply should include useful summary")
        _require("Arrival at Kyoto Station" in voice_reply, "voice last-document reply should include concrete summary detail")
        route = await last_route_text(db_path)
        _require("input: voice note" in route, "voice last-document route should preserve voice input type")
        _require("lane: xAI STT + command" in route, "voice last-document route should show command after STT")

    print("everyday_commands_smoke: ok")


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)
    await init_session_memory_db(db_path)
    await init_context_layers_db(db_path)


if __name__ == "__main__":
    asyncio.run(main())
