from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from office_modern_files import create_docx
from everyday_commands import EverydayCommandRouter
from harness_artifact_store import record_structured_artifact
from harness_models import local_artifact
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
        await init_db(db_path)
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

        imac_open = await router.handle("open the last document", "imac")
        _require(imac_open is not None and "opened" in imac_open.lower(), "iMac open should open the exact last document")
        _require(bridge.opened[-1][0] == str(path), "iMac opened the wrong latest document")

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

    print("everyday_commands_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
