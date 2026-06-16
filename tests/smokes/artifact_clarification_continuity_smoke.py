from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import os
import tempfile
from pathlib import Path

from assistant import KampungAssistant
from context_layers import init_context_layers_db
from harness_artifact_store import init_harness_artifact_db
from harness_store import init_harness_db
from lesson_store import init_lesson_db
from route_tracker import last_route_text
from routine_store import init_routine_db
from semantic_telegram_fresh_fakes import fake_draft, fake_powerpoint_qa, fake_preflight, fake_review
from session_memory_store import init_session_memory_db
from skill_store import init_skill_db
from storage import init_db, save_history_message


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-artifact-continuity-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        os.environ["MAYA_TEST_MODE"] = "1"
        os.environ["MAYA_WORKSPACE_ROOT"] = str(Path(tmp) / "Maya")
        await _init(db_path)

        import document_actions as da
        import travel_budget

        old_preflight = da.artifact_preflight_with_gemini
        old_draft = da.draft_markdown_with_gemini
        old_review = da.review_presentation_slides
        old_pptx = da.create_powerpoint_with_qa
        old_travel_draft = travel_budget.draft_markdown_with_gemini
        try:
            da.artifact_preflight_with_gemini = fake_preflight
            da.draft_markdown_with_gemini = fake_draft
            da.review_presentation_slides = fake_review
            da.create_powerpoint_with_qa = fake_powerpoint_qa
            travel_budget.draft_markdown_with_gemini = fake_draft
            assistant = KampungAssistant(db_path)

            direct = await assistant.handle_text(
                "Hey Maya, um make me a Tokyo food trip Word document for two days.",
                "telegram",
                input_type="voice note",
            )
            _require("[file:" in direct and ".docx" in direct, f"direct Word voice phrase failed: {direct}")
            await _normal_chat_to_word_case(assistant, db_path)
            await _ambiguous_context_confirmation_case(assistant, db_path)
            await _continuity_case(assistant, db_path, "Word document", ".docx")
            await _continuity_case(assistant, db_path, "Excel sheet", ".xlsx")
            await _continuity_case(assistant, db_path, "PowerPoint slides", ".pptx")
        finally:
            da.artifact_preflight_with_gemini = old_preflight
            da.draft_markdown_with_gemini = old_draft
            da.review_presentation_slides = old_review
            da.create_powerpoint_with_qa = old_pptx
            travel_budget.draft_markdown_with_gemini = old_travel_draft
    print("artifact_clarification_continuity_smoke: ok")


async def _normal_chat_to_word_case(assistant: KampungAssistant, db_path: str) -> None:
    await save_history_message(db_path, 1, "user", "Can you make me a two days trip to Kyoto?", "telegram")
    await save_history_message(
        db_path,
        1,
        "assistant",
        "For Kyoto, split two days between Higashiyama, Gion, Arashiyama, Nishiki Market, and Fushimi Inari.",
        "telegram",
    )
    reply = await assistant.handle_text(
        "Okay, can you make me a word document for this?",
        "telegram",
        input_type="voice note",
    )
    _require("[file:" in reply and ".docx" in reply, f"context Word request did not create docx: {reply}")
    _require("kyoto" in reply.lower() or "kyoto" in str(reply).lower(), f"context reply lost Kyoto topic: {reply}")


async def _ambiguous_context_confirmation_case(assistant: KampungAssistant, db_path: str) -> None:
    await save_history_message(db_path, 1, "user", "Can you make me a two days trip to Kyoto?", "telegram")
    await save_history_message(
        db_path,
        1,
        "assistant",
        "For Kyoto, split two days between Higashiyama, Gion, Arashiyama, Nishiki Market, and Fushimi Inari.",
        "telegram",
    )
    first = await assistant.handle_text(
        "Can you make me a document for this?",
        "telegram",
        input_type="voice note",
    )
    _require("Word doc, Excel sheet, or PowerPoint slides" in first, f"missing type clarification: {first}")
    second = await assistant.handle_text("Yes, Word document.", "telegram", input_type="voice note")
    _require("[file:" in second and ".docx" in second, f"yes word document did not consume pending context: {second}")


async def _continuity_case(assistant: KampungAssistant, db_path: str, answer: str, suffix: str) -> None:
    first = await assistant.handle_text(
        "Hey Maya, make me a 2 days Tokyo food trip document for 2 people.",
        "telegram",
        input_type="voice note",
    )
    _require("Word doc, Excel sheet, or PowerPoint slides" in first, f"missing type clarification: {first}")
    _require("make me" not in first.lower(), f"clarification kept command filler: {first}")
    second = await assistant.handle_text(answer, "telegram", input_type="voice note")
    _require("[file:" in second and suffix in second, f"{answer} did not continue pending artifact: {second}")
    route = await last_route_text(db_path)
    _require("input: voice note" in route, f"route did not preserve voice note input: {route}")
    _require("document workflow" in route, f"route did not finish through document workflow: {route}")


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)
    await init_session_memory_db(db_path)
    await init_context_layers_db(db_path)
    await init_harness_db(db_path)
    await init_harness_artifact_db(db_path)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
